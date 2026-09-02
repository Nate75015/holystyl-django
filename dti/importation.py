"""Import d'un DTI reçu de Cultiveau.

L'importeur ne connaît aucune table. Il lit `correspondance.CORRESPONDANCE` et
l'applique : ajouter un modèle à l'échange se fait en déclarant une entrée
là-bas, pas en modifiant ce fichier.

Le déroulé tient en quatre temps.

1. **Vérifier.** Le courriel n'authentifie pas son expéditeur : sans signature
   valide, l'enveloppe est rejetée avant même d'être enregistrée. Une version
   majeure de schéma inconnue l'est aussi — mieux vaut un refus lisible qu'un
   diagnostic relu au jugé.
2. **Enregistrer.** Le payload est archivé tel quel dans `DtiImport`, y compris
   ce qu'Isidor n'exploite pas. Une empreinte déjà reçue n'est pas rejouée.
3. **Rattacher.** L'exploitation est retrouvée par son SIRET. Si personne ne
   correspond, l'import passe en quarantaine : `Exploitation.owner` est
   obligatoire et nul ne peut deviner à quel utilisateur revient un
   diagnostic. Rien n'est perdu, le payload attend un rattachement manuel.
4. **Appliquer.** Création des objets, dans l'ordre des dépendances, en une
   seule transaction. Un import ne laisse jamais un DTI à moitié écrit.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json

from django.apps import apps
from django.conf import settings
from django.db import models as dj
from django.db import transaction

from . import correspondance as corr
from .models import DtiImport


class ImportRefuse(Exception):
    """L'enveloppe ne doit pas entrer : signature, version ou forme."""


# ── 1. Vérification ───────────────────────────────────────────────────────

def _canonique(payload):
    """Doit reproduire octet pour octet la canonicalisation de la source."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def verifier(enveloppe):
    """Signature et version. Lève `ImportRefuse` si l'enveloppe est douteuse."""
    payload = enveloppe.get("payload")
    if not isinstance(payload, dict) or "dti" not in payload:
        raise ImportRefuse("Enveloppe illisible : aucun payload exploitable.")

    secret = (getattr(settings, "IMPORT_DTI_SECRET", "") or "").encode("utf-8")
    if not secret:
        raise ImportRefuse(
            "IMPORT_DTI_SECRET n'est pas configuré : impossible de distinguer "
            "un diagnostic légitime d'un dépôt arbitraire dans la boîte.")

    attendue = hmac.new(secret, _canonique(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(attendue, enveloppe.get("signature") or ""):
        raise ImportRefuse("Signature invalide : l'enveloppe n'a pas été émise "
                           "par une source de confiance, ou a été modifiée.")

    majeur = str(payload.get("schema_version", "")).split(".")[0]
    if majeur != corr.SCHEMA_MAJEUR_SUPPORTE:
        raise ImportRefuse(
            f"Version de schéma {payload.get('schema_version')!r} non gérée "
            f"(majeure {corr.SCHEMA_MAJEUR_SUPPORTE} attendue).")
    return payload


# ── 2. Enregistrement ─────────────────────────────────────────────────────

def _horodatage(valeur):
    if not valeur:
        return None
    try:
        return dt.datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except ValueError:
        return None


def enregistrer(enveloppe):
    """Archive l'enveloppe et retourne (import, deja_connu).

    Un renvoi de même empreinte ne crée pas de doublon : la source déduplique
    déjà, mais un courriel peut être relu deux fois.
    """
    payload = verifier(enveloppe)
    d = payload["dti"]
    exploitation_source = d.get("exploitation") or {}
    empreinte = enveloppe.get("empreinte") or ""

    existant = DtiImport.objects.filter(empreinte=empreinte).first() if empreinte else None
    if existant:
        return existant, True

    return DtiImport.objects.create(
        source=payload.get("source", "cultiveau"),
        schema_version=payload.get("schema_version", ""),
        dti_source_id=d.get("id"),
        exported_at=_horodatage(payload.get("exported_at")),
        empreinte=empreinte,
        payload=payload,
        siret_declare=(exploitation_source.get("siret") or "")[:14],
        nom_declare=(exploitation_source.get("nom")
                     or exploitation_source.get("nom_individu") or "")[:255],
        medias_archive=payload.get("medias_archive"),
        statut=DtiImport.Statut.RECU,
    ), False


# ── 3. Rattachement ───────────────────────────────────────────────────────

def trouver_exploitation(dti_import):
    """L'exploitation Isidor correspondante, par SIRET.

    Le SIRET est le seul identifiant fiable partagé par les deux systèmes ;
    rapprocher sur le nom produirait des faux positifs entre deux exploitations
    du même exploitant.
    """
    if not dti_import.siret_declare:
        return None
    Exploitation = apps.get_model("exploitations.Exploitation")
    return Exploitation.objects.filter(siret=dti_import.siret_declare).first()


# ── 4. Application de la correspondance ───────────────────────────────────

def _convertir(champ, valeur):
    """Adapte une valeur JSON au champ Django visé.

    La source sérialise les décimaux en chaînes et les dates en ISO (§ 2 du
    schéma) : Django accepte les deux, sauf pour les champs numériques stricts
    où une chaîne lève. On convertit donc au vu du champ réel.
    """
    if valeur is None or valeur == "":
        # Un champ texte veut "" et non NULL ; l'inverse pour le reste.
        return "" if isinstance(champ, (dj.CharField, dj.TextField)) else None
    if isinstance(champ, (dj.FloatField, dj.IntegerField)) and isinstance(valeur, str):
        try:
            return float(valeur) if isinstance(champ, dj.FloatField) else int(float(valeur))
        except ValueError:
            return None
    if isinstance(champ, dj.DateTimeField) and isinstance(valeur, str):
        # Une date nue de la source (`2026-07-25`) face à un DateTimeField :
        # on la situe à minuit dans le fuseau du projet plutôt que de laisser
        # Django recevoir un datetime naïf et deviner.
        horodatage = _horodatage(valeur)
        if horodatage is not None and horodatage.tzinfo is None:
            from django.utils import timezone
            horodatage = timezone.make_aware(horodatage)
        return horodatage
    if isinstance(champ, (dj.CharField, dj.TextField)) and not isinstance(valeur, str):
        return str(valeur)
    return valeur


def _appliquer(cible, source, extra=None):
    """Construit le dict de champs d'un objet, `reste_dans` compris."""
    modele = apps.get_model(cible.modele)
    champs = {f.name: f for f in modele._meta.fields}
    valeurs = dict(extra or {})

    for nom_source, nom_cible in cible.champs.items():
        if nom_source not in source:
            continue
        champ = champs.get(nom_cible)
        if champ is None:
            continue
        valeurs[nom_cible] = _convertir(champ, source[nom_source])

    if cible.reste_dans:
        # Tout ce qui n'a pas de colonne dédiée, sous ses noms d'origine. Les
        # collections filles en sont exclues : elles deviennent des objets à
        # part entière, les recopier ici les stockerait deux fois.
        pris = set(cible.champs) | {"id"}
        reste = {}
        for cle, valeur in source.items():
            if cle in pris or valeur in (None, "", [], {}):
                continue
            if isinstance(valeur, list) and valeur and isinstance(valeur[0], dict) \
                    and "id" in valeur[0]:
                continue
            reste[cle] = valeur
        valeurs[cible.reste_dans] = reste
    return valeurs


def _enregistrer_partage(cible, source, extra, rapport, chemin):
    """Crée ou met à jour un objet d'un modèle partagé d'Isidor.

    Ces modèles ne sont pas historisés : une exploitation a UN parcellaire, qui
    évolue. Les recréer à chaque réception ferait quinze parcelles de plus par
    version de diagnostic. L'objet est donc retrouvé sur sa clé naturelle,
    dans le périmètre de son parent.
    """
    modele = apps.get_model(cible.modele)
    valeurs = _appliquer(cible, source, extra)
    if not cible.cle or not valeurs.get(cible.cle):
        rapport[chemin] = rapport.get(chemin, 0) + 1
        return modele.objects.create(**valeurs), True

    recherche = {cible.cle: valeurs.pop(cible.cle)}
    # Le rapprochement se fait dans le périmètre du parent : deux exploitations
    # peuvent porter la même référence cadastrale.
    for lien in ("exploitation", "parcelle"):
        if lien in extra and extra[lien] is not None:
            recherche[lien] = extra[lien]
    objet, cree = modele.objects.update_or_create(defaults=valeurs, **recherche)
    cle_rapport = chemin if cree else f"{chemin} (mis à jour)"
    rapport[cle_rapport] = rapport.get(cle_rapport, 0) + 1
    return objet, cree


@transaction.atomic
def importer(dti_import):
    """Crée les objets du DTI. Tout ou rien.

    Ré-exécutable : les objets de l'app `dti` déjà créés par cet import sont
    purgés d'abord, et les modèles partagés sont rapprochés sur leur clé
    naturelle. Sans cela, rattacher un import déjà passé doublait tout —
    six ressources en eau en devenaient douze.

    Retourne le rapport : combien d'objets par modèle. Un import qui ne crée
    rien doit se voir — sans ce décompte, une correspondance devenue muette
    passerait pour un succès.
    """
    if not dti_import.exploitation:
        raise ImportRefuse("Import sans exploitation rattachée.")

    # Purge de l'instantané précédent de CE import. Les modèles partagés n'y
    # sont pas touchés : ils appartiennent à l'exploitation, pas au diagnostic.
    for chemin, cible in corr.entrees_ordonnees():
        if cible.modele.startswith("dti."):
            apps.get_model(cible.modele).objects.filter(import_dti=dti_import).delete()

    d = dti_import.payload["dti"]
    exploitation = dti_import.exploitation
    rapport = {}
    # Correspondance « id source → objet créé », par chemin : c'est elle qui
    # permet de relier les enfants à leur parent sans dépendre de l'ordre.
    crees = {}

    def noter(chemin, objet, source_id):
        rapport[chemin] = rapport.get(chemin, 0) + 1
        crees.setdefault(chemin, {})[source_id] = objet

    # ── Exploitation : on met à jour l'existante, on n'en crée jamais ──
    cible_exp = corr.CORRESPONDANCE["exploitation"]
    source_exp = d.get("exploitation") or {}
    if source_exp:
        valeurs = _appliquer(cible_exp, source_exp)
        # Le nom et le SIRET identifient l'exploitation côté Isidor : les
        # écraser depuis un diagnostic reviendrait à laisser la source
        # renommer une fiche qui ne lui appartient pas.
        for protege in ("name", "siret"):
            valeurs.pop(protege, None)
        for nom, valeur in valeurs.items():
            if valeur not in (None, ""):
                setattr(exploitation, nom, valeur)
        exploitation.save()
        rapport["exploitation"] = 1

    # ── Parcelles, puis leurs enfants ──
    cible_parc = corr.CORRESPONDANCE["parcelles"]
    for source in d.get("parcelles") or []:
        parcelle, _ = _enregistrer_partage(
            cible_parc, source, {"exploitation": exploitation}, rapport, "parcelles")
        crees.setdefault("parcelles", {})[source.get("id")] = parcelle

        for chemin in ("parcelles.assolements", "parcelles.analyses_satellite"):
            cible = corr.CORRESPONDANCE[chemin]
            modele = apps.get_model(cible.modele)
            cle_liste = chemin.split(".", 1)[1]
            for enfant in source.get(cle_liste) or []:
                extra = {"parcelle": parcelle}
                if any(f.name == "exploitation" for f in modele._meta.fields):
                    extra["exploitation"] = exploitation
                _enregistrer_partage(cible, enfant, extra, rapport, chemin)

    def parcelle_de(source):
        return crees.get("parcelles", {}).get(source.get("parcelle_id"))

    # ── Équipements avant ressources : une borne peut désigner une station ──
    for chemin, cle_parent in (("equipements", None), ("ressources_eau", None),
                               ("canalisations", None), ("mesures_debit", None)):
        cible = corr.CORRESPONDANCE[chemin]
        modele = apps.get_model(cible.modele)
        for source in d.get(chemin) or []:
            extra = {"import_dti": dti_import, "exploitation": exploitation,
                     "source_id": source.get("id")}
            if any(f.name == "parcelle" for f in modele._meta.fields):
                extra["parcelle"] = parcelle_de(source)
            objet = modele.objects.create(**_appliquer(cible, source, extra))
            noter(chemin, objet, source.get("id"))

            # Enfants directs (composants, relevés) déclarés sous « chemin.… »
            for sous_chemin, sous_cible in corr.CORRESPONDANCE.items():
                if (not sous_chemin.startswith(f"{chemin}.")
                        or sous_cible.modele == corr.ARCHIVE_SEULE):
                    continue
                cle_liste = sous_chemin.split(".", 1)[1]
                sous_modele = apps.get_model(sous_cible.modele)
                porteur = ("equipement" if chemin == "equipements" else "ressource")
                for enfant in source.get(cle_liste) or []:
                    sous_modele.objects.create(**_appliquer(sous_cible, enfant, {
                        "import_dti": dti_import, "exploitation": exploitation,
                        "source_id": enfant.get("id"), porteur: objet}))
                    rapport[sous_chemin] = rapport.get(sous_chemin, 0) + 1

    # ── Second passage : le cycle borne ↔ station ne peut se résoudre qu'ici ──
    # Il se referme dans les deux sens : un enrouleur part d'une borne
    # (`borne_source`), et un point d'eau porte la station qui le pompe
    # (`station_pompage`). Ne traiter qu'un sens perdait le second lien.
    liens = 0
    for source in d.get("ressources_eau") or []:
        ressource = crees.get("ressources_eau", {}).get(source.get("id"))
        station = crees.get("equipements", {}).get(source.get("station_pompage_id"))
        if ressource and station:
            ressource.station_pompage = station
            ressource.save(update_fields=["station_pompage"])
            liens += 1

    for source in d.get("equipements") or []:
        objet = crees.get("equipements", {}).get(source.get("id"))
        borne = crees.get("ressources_eau", {}).get(source.get("borne_source_id"))
        if objet and borne:
            objet.borne_source = borne
            objet.save(update_fields=["borne_source"])
            liens += 1
        if objet and source.get("parcelles_desservies"):
            objet.parcelles_desservies.set(
                [p for p in (crees.get("parcelles", {}).get(i)
                             for i in source["parcelles_desservies"]) if p])
    if liens:
        rapport["liens_borne_station"] = liens

    # ── Score : on alimente le modèle existant, pas un jumeau ──
    # DtiScore n'a pas de lien vers l'import et ne peut donc pas être purgé au
    # rejeu. On ne le recrée pas si cet import en a déjà produit un : le
    # contenu serait identique, l'empreinte étant la même.
    indicateurs = dti_import.payload.get("indicateurs") or {}
    if indicateurs.get("score") is not None and not (dti_import.rapport or {}).get("score"):
        DtiScore = apps.get_model("irrigation.DtiScore")
        DtiScore.objects.create(
            exploitation=exploitation,
            score=(indicateurs.get("grade") or "D")[:1],
            score_numeric=float(indicateurs["score"]),
            recommendations=indicateurs.get("lignes"),
        )
        rapport["score"] = 1

    dti_import.rapport = rapport
    dti_import.statut = DtiImport.Statut.IMPORTE
    dti_import.save(update_fields=["rapport", "statut", "updated_at"])
    return rapport


# ── Orchestration ─────────────────────────────────────────────────────────

def recevoir(enveloppe):
    """Point d'entrée : vérifie, archive, rattache et importe si possible.

    Retourne l'import. Son `statut` dit ce qui s'est passé — importé, en
    quarantaine faute d'exploitation connue, ou en erreur.
    """
    dti_import, deja_connu = enregistrer(enveloppe)
    if deja_connu:
        return dti_import

    exploitation = trouver_exploitation(dti_import)
    if not exploitation:
        dti_import.statut = DtiImport.Statut.QUARANTAINE
        dti_import.save(update_fields=["statut", "updated_at"])
        return dti_import

    dti_import.exploitation = exploitation
    dti_import.save(update_fields=["exploitation", "updated_at"])
    try:
        importer(dti_import)
    except Exception as exc:  # l'échec doit rester visible et rejouable
        dti_import.statut = DtiImport.Statut.ERREUR
        dti_import.erreur = f"{type(exc).__name__}: {exc}"
        dti_import.save(update_fields=["statut", "erreur", "updated_at"])
    return dti_import


def rattacher(dti_import, exploitation):
    """Lie un import en quarantaine à une exploitation, puis l'importe.

    C'est le geste que personne ne peut automatiser : décider de qui relève ce
    diagnostic. Une fois posé, l'import se déroule normalement.
    """
    dti_import.exploitation = exploitation
    dti_import.save(update_fields=["exploitation", "updated_at"])
    return importer(dti_import)
