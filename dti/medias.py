"""Récupération des photos d'un diagnostic.

Le JSON d'un DTI tient dans un courriel, ses photos non : elles voyagent dans
une archive ZIP, jointe au message quand elle est petite, déposée sur le
stockage objet sinon. Ce module rapatrie l'une ou l'autre et range les
binaires.

Le chemin d'origine de chaque fichier est conservé (`MediaDti.chemin_source`) :
c'est lui qui relie une photo à l'objet qui la porte, sans table de
correspondance — le payload référence les mêmes chemins.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

from django.core.files.base import ContentFile

from .models import MediaDti


def _porteur(payload, chemin):
    """Retrouve à quel objet du diagnostic appartient un fichier.

    On balaie l'arbre à la recherche du chemin : c'est plus robuste que de
    coder la liste des champs fichier, qui changerait à chaque évolution du
    schéma source.
    """
    trouve = {}

    def descendre(nœud, type_courant=None, id_courant=None):
        if isinstance(nœud, dict):
            id_local = nœud.get("id", id_courant)
            for cle, valeur in nœud.items():
                if valeur == chemin and isinstance(valeur, str):
                    trouve.setdefault("type", type_courant)
                    trouve.setdefault("id", id_local)
                else:
                    descendre(valeur, type_courant, id_local)
        elif isinstance(nœud, list):
            for element in nœud:
                descendre(element, type_courant, id_courant)

    for cle, valeur in (payload.get("dti") or {}).items():
        descendre(valeur, cle, None)
    return trouve.get("type", ""), trouve.get("id")


def enregistrer_manifeste(dti_import):
    """Crée une entrée `MediaDti` par fichier annoncé, binaire ou non.

    Les fichiers introuvables à la source sont enregistrés avec `manquant` :
    la cible doit pouvoir distinguer « pas de photo » de « photo perdue ».
    """
    payload = dti_import.payload
    crees = 0
    for entree in payload.get("medias") or []:
        chemin = entree.get("path")
        if not chemin:
            continue
        type_porteur, id_porteur = _porteur(payload, chemin)
        MediaDti.objects.update_or_create(
            import_dti=dti_import, chemin_source=chemin,
            defaults={
                "sha256": entree.get("sha256", ""),
                "octets": entree.get("bytes"),
                "manquant": bool(entree.get("manquant")),
                "porteur_type": type_porteur or "",
                "porteur_source_id": id_porteur,
            })
        crees += 1
    return crees


def deballer_archive(dti_import, octets_zip):
    """Range les binaires de l'archive sur les `MediaDti` correspondants.

    L'empreinte de chaque fichier est vérifiée : une archive tronquée en cours
    de transfert doit se voir, pas produire des photos corrompues qu'on
    découvrirait à l'affichage.
    """
    ranges = ignores = 0
    with zipfile.ZipFile(io.BytesIO(octets_zip)) as zf:
        for media in dti_import.medias.filter(manquant=False):
            try:
                contenu = zf.read(media.chemin_source)
            except KeyError:
                ignores += 1
                continue
            if media.sha256 and hashlib.sha256(contenu).hexdigest() != media.sha256:
                ignores += 1
                continue
            nom = media.chemin_source.rsplit("/", 1)[-1]
            media.fichier.save(nom, ContentFile(contenu), save=True)
            ranges += 1

    dti_import.medias_recuperes = ranges > 0 and ignores == 0
    dti_import.save(update_fields=["medias_recuperes", "updated_at"])
    return ranges, ignores


def telecharger_depuis_objet(dti_import, timeout=30):
    """Rapatrie l'archive déposée sur le stockage objet.

    L'URL signée a une durée de vie limitée : un import rejoué des semaines
    plus tard ne retrouvera pas les photos, et devra être réémis. C'est un
    compromis assumé — une URL éternelle resterait exploitable si elle fuitait.
    """
    import urllib.request

    archive = dti_import.medias_archive or {}
    url = archive.get("url")
    if not url:
        return None
    with urllib.request.urlopen(url, timeout=timeout) as reponse:  # noqa: S310
        return reponse.read()


def recuperer(dti_import, octets_joints=None):
    """Point d'entrée : manifeste, puis binaires selon le mode d'acheminement."""
    enregistrer_manifeste(dti_import)
    archive = dti_import.medias_archive or {}
    if not archive:
        return 0, 0

    octets = octets_joints
    if octets is None and archive.get("mode") == "objet":
        octets = telecharger_depuis_objet(dti_import)
    if octets is None:
        return 0, 0
    return deballer_archive(dti_import, octets)
