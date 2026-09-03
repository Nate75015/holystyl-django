"""Lecture d'une pièce d'identité (PDF ou photo) par l'IA.

Même principe que la lecture d'un bail ou d'un acte : on donne le document au
modèle multimodal et on récupère des champs. Repli propre — si l'IA n'est pas
configurée ou si le fichier n'est pas exploitable, on renvoie None et le
document est simplement archivé, sans valeur inventée.

Deux différences avec les autres lectures du projet, qui tiennent à la nature
de la pièce :

On ne demande que ce que l'application range. Ni date de naissance, ni
adresse, ni taille : elles figurent sur la carte mais n'ont aucun usage ici,
et chaque champ extrait est une donnée personnelle de plus à protéger.

Et on ne lit jamais la puce ni les empreintes : seul ce qui est imprimé.
"""

from __future__ import annotations

import os

from ia import llm

_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

_PROMPT = (
    "Tu lis une pièce d'identité française : carte nationale d'identité "
    "(ancien format plastifié ou nouveau format carte bancaire depuis 2021) "
    "ou passeport. Extrais uniquement les informations demandées, en JSON "
    "strict. Mets null pour tout ce que le document ne montre pas — n'invente "
    "jamais une valeur, surtout pas une date ni un numéro.\n"
    "N'extrais rien d'autre que les clés listées : ignore la date et le lieu "
    "de naissance, l'adresse, la taille, le sexe et la photographie.\n"
    "Clés attendues :\n"
    "- type_piece : « carte » pour une carte nationale d'identité, "
    "« passeport » pour un passeport\n"
    "- titulaire : les prénoms suivis du nom de famille, en une ligne\n"
    "- nom_usage : le nom d'usage s'il figure et diffère du nom de famille, "
    "sinon null\n"
    "- numero : le numéro du document — douze chiffres sur l'ancienne carte, "
    "neuf caractères sur la nouvelle, neuf caractères sur un passeport\n"
    "- autorite : l'autorité de délivrance (préfecture, sous-préfecture, "
    "mairie ou consulat), telle qu'elle est écrite\n"
    "- delivre_le, expire_le : au format AAAA-MM-JJ\n"
    "La zone de lecture automatique en bas du document (deux ou trois lignes "
    "de caractères et de chevrons) donne le nom, les prénoms, le numéro et la "
    "date d'expiration : sers-t'en pour vérifier ce que tu as lu ailleurs."
)

TEXTE = ("type_piece", "titulaire", "nom_usage", "numero", "autorite")
DATES = ("delivre_le", "expire_le")

CHAMPS = TEXTE + DATES


def lire(data: bytes, nom_fichier: str) -> dict | None:
    """Les champs lus dans le document, ou None si rien n'est exploitable."""
    if not llm.is_configured() or not data:
        return None
    mime = _MIME.get(os.path.splitext(nom_fichier)[1].lower())
    if not mime:
        return None  # type non lisible par le modèle
    try:
        brut = llm.extract_json_from_document(data, mime, _PROMPT)
    except Exception:  # noqa: BLE001 — toute erreur IA → repli silencieux
        return None
    if not brut:
        return None

    champs = {cle: brut.get(cle) for cle in CHAMPS}
    # Le modèle peut proposer un type hors référentiel : on ne le laisse pas
    # décider seul de la nature de la pièce.
    from .models import Piece

    if champs["type_piece"] not in (Piece.Type.CARTE, Piece.Type.PASSEPORT):
        champs["type_piece"] = None
    return champs
