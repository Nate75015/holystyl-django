"""Lecture d'un acte notarié (PDF ou photo) par l'IA.

Même principe que la lecture d'un bail : on donne le document au modèle
multimodal et on récupère des champs. Repli propre — si l'IA n'est pas
configurée ou si le fichier n'est pas exploitable, on renvoie None et le
document est simplement archivé, sans valeur inventée.

Ce que le modèle propose n'est jamais écrit tel quel : la vue pré-remplit le
formulaire, l'exploitant relit et valide. Un acte notarié se lit mal en
diagonale, et une date de réitération mal recopiée rend le compromis caduc.
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
    "Tu lis un acte notarié français concernant une exploitation agricole "
    "(vente, achat, échange, donation, succession, partage, servitude, "
    "hypothèque, mainlevée, constitution de société, promesse ou compromis). "
    "Extrais les informations en JSON strict. Mets null pour tout ce que le "
    "document ne dit pas — n'invente jamais une valeur, surtout pas un montant "
    "ni une date.\n"
    "Clés attendues :\n"
    "- objet : ce sur quoi porte l'acte, en une ligne\n"
    "- type_acte : une valeur parmi vente, achat, echange, donation, "
    "donation_partage, succession, partage, testament, demembrement, servitude, "
    "hypotheque, mainlevee, pret, bail_emphyteotique, societe, apport, "
    "attestation, procuration, autre\n"
    "- statut : projet, promesse, signe, publie ou caduc — « promesse » si le "
    "document est un avant-contrat, « signe » s'il s'agit de l'acte authentique\n"
    "- notaire : le nom de l'étude ou du notaire instrumentaire\n"
    "- telephone_notaire, email_notaire : les coordonnées de l'étude\n"
    "- parties : vendeur et acquéreur, donateur et donataire, en une ligne\n"
    "- reference : le numéro de répertoire ou la référence de l'acte\n"
    "- date_promesse, date_limite_realisation, date_signature, date_publication, "
    "date_peremption : au format AAAA-MM-JJ\n"
    "- mainlevee_obtenue : true ou false\n"
    "- surface_ha : la surface totale en hectares, un nombre\n"
    "- references_cadastrales : section et numéros, en texte court\n"
    "- montant, frais_notaire, droits_enregistrement : des nombres, sans devise "
    "ni espace\n"
    "- conditions_suspensives : les conditions dont dépend la réitération, en "
    "texte court\n"
    "- charges_et_servitudes : servitudes de passage, de vue, d'écoulement, "
    "charges grevant le bien, en texte court\n"
    "- droit_preemption : ce que l'acte dit d'un droit de préemption (SAFER, "
    "preneur en place, commune), en texte court"
)

TEXTE = (
    "objet", "type_acte", "statut", "notaire", "telephone_notaire",
    "email_notaire", "parties", "reference", "references_cadastrales",
    "conditions_suspensives", "charges_et_servitudes", "droit_preemption",
)
DATES = ("date_promesse", "date_limite_realisation", "date_signature",
         "date_publication", "date_peremption")
NOMBRES = ("surface_ha", "montant", "frais_notaire", "droits_enregistrement")
BOOLEENS = ("mainlevee_obtenue",)

CHAMPS = TEXTE + DATES + NOMBRES + BOOLEENS


def lire(data: bytes, nom_fichier: str) -> dict | None:
    """Les champs lus dans le document, ou None si rien n'est exploitable."""
    if not llm.is_configured() or not data:
        return None
    mime = _MIME.get(os.path.splitext(nom_fichier)[1].lower())
    if not mime:
        return None  # type non lisible par le modèle (docx, xls…)
    try:
        brut = llm.extract_json_from_document(data, mime, _PROMPT)
    except Exception:  # noqa: BLE001 — toute erreur IA → repli silencieux
        return None
    if not brut:
        return None
    return {cle: brut.get(cle) for cle in CHAMPS}
