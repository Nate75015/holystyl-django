"""Contrat d'échange avec Cultiveau.

Ces tests ne vérifient pas du code : ils vérifient qu'une correspondance
déclarée reste applicable. C'est ce qui permet de faire évoluer les deux
schémas sans découvrir la casse six mois plus tard, sur des imports
silencieusement tronqués.

`dti/fixtures/dti_reference.json` est un export réel anonymisé. Il est le
spécimen contre lequel la correspondance est éprouvée ; le régénérer après une
évolution du schéma se fait côté Cultiveau, par
`manage.py exporter_dti <id> --sortie …`.
"""

import json
from pathlib import Path

from django.apps import apps
from django.test import TestCase

from . import correspondance as corr

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dti_reference.json"


def charger_reference():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FixtureDeReferenceTests(TestCase):
    """Le spécimen doit rester un export plausible et anonyme."""

    def test_fixture_presente_et_versionnee(self):
        env = charger_reference()
        self.assertIn("payload", env)
        self.assertEqual(env["payload"]["schema_version"].split(".")[0],
                         corr.SCHEMA_MAJEUR_SUPPORTE)

    def test_fixture_ne_porte_pas_de_donnees_reelles(self):
        """Un dépôt n'est pas l'endroit où stocker le SIRET d'un exploitant."""
        env = charger_reference()
        exploitation = env["payload"]["dti"]["exploitation"]
        self.assertEqual(exploitation["siret"], "00000000000000")
        self.assertNotIn("@gmail", json.dumps(env))

    def test_fixture_est_un_specimen_complet(self):
        """Une fixture vide ne prouverait rien : elle doit exercer les chemins
        qui comptent — rattachement, parcellaire, hydraulique, matériel."""
        d = charger_reference()["payload"]["dti"]
        self.assertTrue(d["exploitation"]["siret"])
        self.assertGreater(len(d["parcelles"]), 0)
        self.assertGreater(len(d["ressources_eau"]), 0)
        self.assertGreater(len(d["equipements"]), 0)


class CorrespondanceTests(TestCase):
    """La table de correspondance doit rester applicable telle qu'écrite."""

    def test_modeles_cibles_existent(self):
        """Une cible mal orthographiée ne doit pas se découvrir en production."""
        for chemin, cible in corr.entrees_ordonnees():
            with self.subTest(chemin=chemin):
                try:
                    apps.get_model(cible.modele)
                except LookupError:
                    self.fail(f"« {chemin} » vise « {cible.modele} », qui n'existe pas.")

    def test_champs_cibles_existent(self):
        """Le garde-fou décisif : un champ renommé côté Holystyl casse ici, et
        non à l'import du prochain diagnostic."""
        for chemin, cible in corr.entrees_ordonnees():
            modele = apps.get_model(cible.modele)
            noms = {f.name for f in modele._meta.get_fields()}
            for source, destination in cible.champs.items():
                with self.subTest(chemin=chemin, champ=destination):
                    self.assertIn(
                        destination, noms,
                        f"« {chemin} » écrit dans {cible.modele}.{destination}, "
                        f"qui n'existe pas (source : {source}).")

    def test_champ_de_reste_est_un_json(self):
        for chemin, cible in corr.entrees_ordonnees():
            if not cible.reste_dans:
                continue
            modele = apps.get_model(cible.modele)
            champ = modele._meta.get_field(cible.reste_dans)
            self.assertEqual(champ.get_internal_type(), "JSONField", chemin)

    def test_cle_de_rapprochement_existe(self):
        for chemin, cible in corr.entrees_ordonnees():
            if not cible.cle:
                continue
            modele = apps.get_model(cible.modele)
            noms = {f.name for f in modele._meta.get_fields()}
            self.assertIn(cible.cle, noms, f"clé de « {chemin} »")

    def test_archive_seule_est_motivee(self):
        """Écarter une table est un choix ; il doit être écrit, sinon rien ne
        distingue « pas encore exploité » de « oublié »."""
        for chemin, cible in corr.CORRESPONDANCE.items():
            if cible.modele == corr.ARCHIVE_SEULE:
                self.assertTrue(cible.note.strip(),
                                f"« {chemin} » est archivé sans raison déclarée.")


class CouvertureDuPayloadTests(TestCase):
    """Tout ce que la source émet doit être déclaré — importé ou archivé.

    C'est le pendant du test de couverture des modèles côté Cultiveau. Là-bas,
    on garantit qu'un modèle ajouté entre bien dans l'export ; ici, qu'il ne
    tombe pas dans un angle mort à l'arrivée.
    """

    #: Clés scalaires de la racine DTI : métadonnées de l'objet lui-même, pas
    #: des tables filles. Elles sont portées par DtiImport.
    RACINE_SCALAIRE = {"id", "nom", "created_at", "updated_at"}

    @staticmethod
    def _est_une_ligne(valeur):
        """Distingue une ligne de table d'une colonne JSON.

        Les deux se présentent comme des dicts, et une colonne JSON peut même
        être une liste de dicts (`equipements.arroseurs`, `secteurs`…). Le
        départage tient à l'identifiant : la source conserve l'`id` d'origine
        de chaque ligne comme identifiant de corrélation, quand ses colonnes
        JSON n'en portent pas.
        """
        return isinstance(valeur, dict) and "id" in valeur

    def _chemins_du_payload(self, nœud, prefixe=""):
        """Les chemins de tables filles présents dans le payload."""
        trouves = set()
        for cle, valeur in nœud.items():
            if prefixe == "" and cle in self.RACINE_SCALAIRE:
                continue
            chemin = f"{prefixe}{cle}"
            if isinstance(valeur, list) and valeur and self._est_une_ligne(valeur[0]):
                trouves.add(chemin)
                # Toute la collection, pas seulement sa première ligne : une
                # borne sans photo suivie d'un forage qui en porte une ferait
                # sinon passer « ressources_eau.photos » pour non émis.
                for ligne in valeur:
                    trouves |= self._chemins_du_payload(ligne, f"{chemin}.")
            elif self._est_une_ligne(valeur):
                trouves.add(chemin)
                trouves |= self._chemins_du_payload(valeur, f"{chemin}.")
        return trouves

    def test_toute_collection_du_payload_est_declaree(self):
        d = charger_reference()["payload"]["dti"]
        presents = self._chemins_du_payload(d)
        # Les collections vides du spécimen n'apparaissent pas : on les ajoute
        # depuis la racine pour que la couverture ne dépende pas du contenu.
        presents |= {c for c in d if isinstance(d[c], list)}
        non_declares = {c for c in presents
                        if c not in corr.chemins_declares()
                        and not c.endswith("_desservies")}
        self.assertEqual(
            non_declares, set(),
            f"Chemin(s) émis par la source mais non déclaré(s) : "
            f"{sorted(non_declares)}. Ajoutez-les à CORRESPONDANCE — avec "
            f"ARCHIVE_SEULE et une raison si Holystyl ne les exploite pas.")

    def test_version_majeure_inconnue_serait_rejetee(self):
        env = charger_reference()
        majeur = env["payload"]["schema_version"].split(".")[0]
        self.assertEqual(majeur, corr.SCHEMA_MAJEUR_SUPPORTE)
        self.assertNotEqual("2", corr.SCHEMA_MAJEUR_SUPPORTE,
                            "Pensez à relire la correspondance avant de passer "
                            "à un schéma majeur suivant.")


class EnveloppeSigneeMixin:
    """Prépare une enveloppe signée et de quoi la rattacher.

    Un mixin, pas une classe de base : hériter d'un TestCase ferait rejouer
    tous ses tests dans chaque sous-classe.
    """

    SECRET = "secret-de-test"

    def setUp(self):
        import hashlib
        import hmac
        import json as _json
        from django.contrib.auth import get_user_model
        from django.test import override_settings

        self.reglages = override_settings(IMPORT_DTI_SECRET=self.SECRET)
        self.reglages.enable()
        self.addCleanup(self.reglages.disable)

        self.enveloppe = charger_reference()
        payload = self.enveloppe["payload"]
        # La fixture est livrée sans signature (elle serait invalide après
        # anonymisation) : on la signe ici avec le secret de test.
        octets = _json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        self.enveloppe["signature"] = hmac.new(
            self.SECRET.encode(), octets, hashlib.sha256).hexdigest()

        self.User = get_user_model()
        self.utilisateur = self.User.objects.create_user(
            email="operateur@example.invalid", password="x")

    def _exploitation(self, siret="00000000000000"):
        from exploitations.models import Exploitation
        return Exploitation.objects.create(
            owner=self.utilisateur, name="Exploitation de test", siret=siret)


class ImportationTests(EnveloppeSigneeMixin, TestCase):
    """Réception d'un diagnostic, de bout en bout.

    Tout se joue sur base éphémère : ces scénarios créent et détruisent des
    parcelles, et n'ont rien à faire dans une base de travail.
    """

    # ── Garde-fous d'entrée ──

    def test_signature_invalide_refusee(self):
        """Le courriel n'authentifie pas l'expéditeur : sans signature valide,
        déposer un faux diagnostic suffirait à écrire en base."""
        from . import importation
        self.enveloppe["signature"] = "0" * 64
        with self.assertRaises(importation.ImportRefuse):
            importation.recevoir(self.enveloppe)

    def test_payload_altere_apres_signature_refuse(self):
        from . import importation
        self.enveloppe["payload"]["dti"]["nom"] = "Diagnostic falsifié"
        with self.assertRaises(importation.ImportRefuse):
            importation.recevoir(self.enveloppe)

    def test_version_majeure_inconnue_refusee(self):
        from . import importation
        self.enveloppe["payload"]["schema_version"] = "9.0"
        with self.assertRaises(importation.ImportRefuse):
            importation.recevoir(self.enveloppe)

    def test_sans_secret_configure_rien_ne_passe(self):
        from django.test import override_settings
        from . import importation
        with override_settings(IMPORT_DTI_SECRET=""):
            with self.assertRaises(importation.ImportRefuse):
                importation.recevoir(self.enveloppe)

    # ── Quarantaine et rattachement ──

    def test_siret_inconnu_met_en_quarantaine(self):
        """Exploitation.owner est obligatoire : nul ne peut deviner à quel
        utilisateur revient un diagnostic. Rien n'est perdu pour autant."""
        from . import importation
        from .models import DtiImport, RessourceEau
        imp = importation.recevoir(self.enveloppe)
        self.assertEqual(imp.statut, DtiImport.Statut.QUARANTAINE)
        self.assertTrue(imp.payload, "le payload doit être conservé intégralement")
        self.assertEqual(imp.siret_declare, "00000000000000")
        self.assertEqual(RessourceEau.objects.count(), 0)

    def test_rattachement_declenche_l_import(self):
        from . import importation
        from .models import Composant, DtiImport, Equipement, RessourceEau
        imp = importation.recevoir(self.enveloppe)
        exploitation = self._exploitation()
        importation.rattacher(imp, exploitation)
        imp.refresh_from_db()
        self.assertEqual(imp.statut, DtiImport.Statut.IMPORTE)
        self.assertEqual(RessourceEau.objects.count(), 2)
        self.assertEqual(Equipement.objects.count(), 2)
        self.assertEqual(Composant.objects.count(), 2)

    def test_siret_connu_importe_directement(self):
        from . import importation
        from .models import DtiImport
        self._exploitation()
        imp = importation.recevoir(self.enveloppe)
        self.assertEqual(imp.statut, DtiImport.Statut.IMPORTE)
        self.assertTrue(imp.rapport)

    # ── Idempotence : les deux défauts trouvés à l'aller-retour ──

    def test_reimport_ne_duplique_pas_l_instantane(self):
        """Rattacher un import déjà passé doublait tout : six ressources en
        eau en devenaient douze."""
        from . import importation
        from .models import RessourceEau
        exploitation = self._exploitation()
        imp = importation.recevoir(self.enveloppe)
        avant = RessourceEau.objects.count()
        importation.importer(imp)
        self.assertEqual(RessourceEau.objects.count(), avant)

    def test_deux_versions_ne_dupliquent_pas_le_parcellaire(self):
        """Le défaut le plus grave : sans clé naturelle, chaque nouvelle
        version d'un diagnostic ajoutait quinze parcelles de plus.

        Une exploitation a UN parcellaire, qui évolue ; le diagnostic, lui,
        est historisé.
        """
        import hashlib
        import hmac
        import json as _json
        from copy import deepcopy
        from parcelles.models import Parcelle
        from . import importation
        from .models import DtiImport, RessourceEau

        exploitation = self._exploitation()
        importation.recevoir(self.enveloppe)
        parcelles_v1 = Parcelle.objects.filter(exploitation=exploitation).count()

        # Seconde version du même DTI : une valeur change, l'empreinte aussi.
        v2 = deepcopy(self.enveloppe)
        v2["payload"]["dti"]["parcelles"][0]["surface_ha"] = "13.75"
        v2["empreinte"] = "b" * 64
        octets = _json.dumps(v2["payload"], sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        v2["signature"] = hmac.new(self.SECRET.encode(), octets,
                                   hashlib.sha256).hexdigest()
        importation.recevoir(v2)

        self.assertEqual(Parcelle.objects.filter(exploitation=exploitation).count(),
                         parcelles_v1, "le parcellaire ne doit pas être dupliqué")
        self.assertEqual(DtiImport.objects.count(), 2,
                         "chaque réception reste historisée")
        self.assertEqual(RessourceEau.objects.count(), 4,
                         "l'instantané du diagnostic, lui, est bien historisé")
        parcelle = Parcelle.objects.get(exploitation=exploitation,
                                        cadastral_ref="000A0000")
        self.assertEqual(parcelle.area, 13.75, "la mise à jour doit s'appliquer")

    def test_meme_enveloppe_relue_ne_cree_pas_de_doublon(self):
        """Un courriel peut être relu deux fois."""
        from . import importation
        from .models import DtiImport
        self._exploitation()
        a = importation.recevoir(self.enveloppe)
        b = importation.recevoir(self.enveloppe)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(DtiImport.objects.count(), 1)

    # ── Fidélité du contenu ──

    def test_le_cycle_borne_station_est_resolu_dans_les_deux_sens(self):
        """RessourceEau.station_pompage et Equipement.borne_source forment un
        cycle : il ne peut se refermer qu'en second passage.

        Les deux sens comptent — un point d'eau porte la station qui le pompe,
        un enrouleur part d'une borne. N'en traiter qu'un perdait l'autre sans
        que rien ne le signale.
        """
        from . import importation
        from .models import Equipement, RessourceEau
        self._exploitation()
        importation.recevoir(self.enveloppe)

        forage = RessourceEau.objects.get(
            categorie=RessourceEau.Categorie.PRELEVEMENT)
        self.assertIsNotNone(forage.station_pompage,
                             "le point d'eau doit retrouver sa station")
        self.assertEqual(forage.station_pompage.type_equipement, "Station de pompage")

        borne = RessourceEau.objects.get(categorie=RessourceEau.Categorie.BORNE)
        self.assertTrue(borne.equipements_alimentes.exists(),
                        "l'enrouleur doit retrouver sa borne d'alimentation")
        self.assertEqual(borne.equipements_alimentes.first().type_equipement,
                         "Enrouleur")

    def test_champs_hors_colonnes_atterrissent_en_caracteristiques(self):
        """Les 175 colonnes polymorphes de l'équipement ne deviennent pas 175
        colonnes ici, mais rien n'est perdu."""
        from . import importation
        from .models import Equipement
        self._exploitation()
        importation.recevoir(self.enveloppe)
        eq = Equipement.objects.get(type_equipement="Station de pompage")
        self.assertIsInstance(eq.caracteristiques, dict)
        # Les colonnes propres au type ne disparaissent pas, elles changent
        # seulement de place : elles gardent leurs noms d'origine.
        self.assertNotIn("type_equipement", eq.caracteristiques)

    def test_le_score_alimente_le_modele_existant(self):
        from irrigation.models import DtiScore
        from . import importation
        exploitation = self._exploitation()
        importation.recevoir(self.enveloppe)
        self.assertEqual(DtiScore.objects.filter(exploitation=exploitation).count(), 1)

    def test_exploitation_non_renommee_par_un_diagnostic(self):
        """La source ne doit pas pouvoir renommer une fiche qui ne lui
        appartient pas."""
        from . import importation
        exploitation = self._exploitation()
        importation.recevoir(self.enveloppe)
        exploitation.refresh_from_db()
        self.assertEqual(exploitation.name, "Exploitation de test")

    def test_rapport_denombre_ce_qui_a_ete_cree(self):
        """Un import qui ne crée rien doit se voir."""
        from . import importation
        self._exploitation()
        imp = importation.recevoir(self.enveloppe)
        self.assertGreaterEqual(imp.rapport.get("ressources_eau", 0), 2)
        self.assertGreaterEqual(imp.rapport.get("parcelles", 0), 1)


class EcranRattachementTests(EnveloppeSigneeMixin, TestCase):
    """L'écran qui porte le seul geste non automatisable de la chaîne."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.utilisateur)

    def test_liste_met_la_quarantaine_en_tete(self):
        from . import importation
        importation.recevoir(self.enveloppe)
        reponse = self.client.get("/dti/receptions/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.context["quarantaine"]), 1)

    def test_detail_montre_le_contenu_avant_import(self):
        """Rattacher à l'aveugle un dossier identifié par un seul numéro serait
        demander à l'opérateur de signer sans lire."""
        from . import importation
        imp = importation.recevoir(self.enveloppe)
        reponse = self.client.get(f"/dti/receptions/{imp.pk}/")
        self.assertEqual(reponse.status_code, 200)
        apercu = dict(reponse.context["apercu"])
        self.assertEqual(apercu["ressources en eau"], 2)
        self.assertEqual(apercu["parcelles"], 1)

    def test_rattachement_importe_et_confirme(self):
        from . import importation
        from .models import DtiImport, RessourceEau
        imp = importation.recevoir(self.enveloppe)
        exploitation = self._exploitation()
        reponse = self.client.post(f"/dti/receptions/{imp.pk}/rattacher/",
                                   {"exploitation": exploitation.pk}, follow=True)
        self.assertEqual(reponse.status_code, 200)
        imp.refresh_from_db()
        self.assertEqual(imp.statut, DtiImport.Statut.IMPORTE)
        self.assertEqual(RessourceEau.objects.count(), 2)

    def test_rattacher_une_exploitation_d_autrui_est_refuse(self):
        from django.contrib.auth import get_user_model
        from exploitations.models import Exploitation
        from . import importation
        imp = importation.recevoir(self.enveloppe)
        autre = get_user_model().objects.create_user(
            email="autre@example.invalid", password="x")
        pas_a_moi = Exploitation.objects.create(owner=autre, name="Chez autrui")
        reponse = self.client.post(f"/dti/receptions/{imp.pk}/rattacher/",
                                   {"exploitation": pas_a_moi.pk})
        self.assertEqual(reponse.status_code, 404)

    def test_rattacher_deux_fois_ne_reimporte_pas(self):
        from . import importation
        imp = importation.recevoir(self.enveloppe)
        exploitation = self._exploitation()
        self.client.post(f"/dti/receptions/{imp.pk}/rattacher/",
                         {"exploitation": exploitation.pk})
        reponse = self.client.post(f"/dti/receptions/{imp.pk}/rattacher/",
                                   {"exploitation": exploitation.pk}, follow=True)
        self.assertContains(reponse, "déjà rattaché")


class MediasTests(EnveloppeSigneeMixin, TestCase):
    """Les photos suivent le diagnostic, ou leur absence est explicite."""

    def _archive(self, chemins):
        import io
        import zipfile
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as zf:
            for chemin in chemins:
                zf.writestr(chemin, b"contenu-photo")
        return tampon.getvalue()

    def test_manifeste_cree_une_entree_par_fichier(self):
        from . import importation, medias
        from .models import MediaDti
        self._exploitation()
        imp = importation.recevoir(self.enveloppe)
        medias.enregistrer_manifeste(imp)
        attendu = len(imp.payload.get("medias") or [])
        self.assertEqual(MediaDti.objects.filter(import_dti=imp).count(), attendu)
        self.assertGreater(attendu, 0)

    def test_archive_alteree_est_rejetee_fichier_par_fichier(self):
        """Une archive tronquée doit se voir, pas produire des photos
        corrompues qu'on découvrirait à l'affichage."""
        from . import importation, medias
        self._exploitation()
        imp = importation.recevoir(self.enveloppe)
        chemins = [m["path"] for m in imp.payload["medias"] if not m.get("manquant")]
        ranges, ignores = medias.recuperer(imp, octets_joints=self._archive(chemins))
        # Le contenu ne correspond pas aux empreintes annoncées : tout est
        # écarté, et l'import n'est pas marqué comme ayant ses médias.
        self.assertEqual(ranges, 0)
        self.assertEqual(ignores, len(chemins))
        imp.refresh_from_db()
        self.assertFalse(imp.medias_recuperes)

    def test_media_absent_a_la_source_reste_signale(self):
        from . import importation, medias
        from .models import MediaDti
        self._exploitation()
        self.enveloppe["payload"]["medias"].append(
            {"path": "parcelles/2026/08/perdue.png", "manquant": True})
        # L'enveloppe change : il faut la resigner.
        import hashlib, hmac, json as _json
        octets = _json.dumps(self.enveloppe["payload"], sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False).encode()
        self.enveloppe["signature"] = hmac.new(
            self.SECRET.encode(), octets, hashlib.sha256).hexdigest()
        imp = importation.recevoir(self.enveloppe)
        medias.enregistrer_manifeste(imp)
        perdue = MediaDti.objects.get(chemin_source="parcelles/2026/08/perdue.png")
        self.assertTrue(perdue.manquant)


class IngestionTests(TestCase):
    """Relève de la boîte : le branchement, pas Gmail lui-même."""

    def test_ingestion_inactive_sans_boite_configuree(self):
        from django.test import override_settings
        from . import ingestion
        with override_settings(IMPORT_DTI_BOITE=""):
            self.assertEqual(ingestion.relever()["etat"], "inactif")
