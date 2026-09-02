"""Lecture d'une police d'assurance (PDF ou photo) par l'IA.

Même principe que l'extraction des analyses de sol : on donne le document au
modèle multimodal et on récupère des champs. Repli propre — si l'IA n'est pas
configurée ou si le fichier n'est pas exploitable, on renvoie None et le
document est simplement archivé, sans valeur inventée.

Ce que le modèle propose n'est jamais écrit tel quel : la vue pré-remplit le
formulaire, l'exploitant relit et valide. Un contrat d'assurance se lit mal en
diagonale, et une franchise mal recopiée se découvre le jour du sinistre.
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
    "Tu lis un contrat d'assurance d'une exploitation agricole française (police, "
    "conditions particulières, avenant ou attestation). Extrais les informations en "
    "JSON strict. Mets null pour tout ce que le document ne dit pas — n'invente "
    "jamais une valeur, surtout pas un montant ni un délai.\n"
    "Clés attendues :\n"
    "- intitule : l'objet du contrat, en une ligne\n"
    "- assureur : la compagnie (Groupama, Crédit Agricole, AXA, Allianz, MAAF…)\n"
    "- courtier : l'agence ou le courtier intermédiaire, s'il diffère\n"
    "- numero_police : le numéro de contrat ou de police\n"
    "- type_assurance : une valeur parmi multirisque, recolte, grele, rc, "
    "rc_dirigeant, vehicules, materiel, batiments, betail, perte_exploitation, "
    "protection_juridique, environnement, sante_prevoyance, emprunteur, "
    "construction, transport, cyber, autre\n"
    "- date_debut, date_fin : au format AAAA-MM-JJ\n"
    "- prime_annuelle, capital_assure, plafond : des nombres, sans devise ni espace\n"
    "- franchise : conserve le texte tel quel (« 10 % avec un minimum de 500 € »)\n"
    "- delai_declaration_jours : un entier, le délai pour déclarer un sinistre\n"
    "- preavis_resiliation_jours : un entier, le préavis de résiliation\n"
    "- tacite_reconduction : true ou false\n"
    "- telephone_sinistre, email_sinistre, telephone_courtier, email_courtier\n"
    "- garanties : la liste de ce qui est couvert, en texte court\n"
    "- exclusions : ce qui est explicitement exclu, en texte court\n"
    "- procedure_sinistre : la marche à suivre pour déclarer, en texte court"
)

TEXTE = (
    "intitule", "assureur", "courtier", "numero_police", "type_assurance",
    "franchise", "telephone_sinistre", "email_sinistre", "telephone_courtier",
    "email_courtier", "garanties", "exclusions", "procedure_sinistre",
)
DATES = ("date_debut", "date_fin")
NOMBRES = ("prime_annuelle", "capital_assure", "plafond")
ENTIERS = ("delai_declaration_jours", "preavis_resiliation_jours")
BOOLEENS = ("tacite_reconduction",)

CHAMPS = TEXTE + DATES + NOMBRES + ENTIERS + BOOLEENS


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
