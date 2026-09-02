"""Lecture d'un bail rural (PDF ou photo) par l'IA.

Même principe que pour les polices d'assurance : le modèle multimodal lit le
document, on récupère des champs, l'exploitant relit avant d'enregistrer.

Un bail se joue sur des délais longs — dix-huit mois de préavis pour donner
congé — et sur des montants encadrés par arrêté préfectoral. Une date mal
recopiée ne se découvre qu'au renouvellement, neuf ans plus tard.
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
    "Tu lis un bail rural français (bail à ferme, bail à long terme, convention "
    "de pâturage, commodat…). Extrais les informations en JSON strict. Mets null "
    "pour tout ce que le document ne dit pas — n'invente jamais une date, une "
    "surface ni un montant.\n"
    "Clés attendues :\n"
    "- designation : l'objet du bail, en une ligne\n"
    "- type_bail : une valeur parmi ferme_9, long_terme_18, long_terme_25, "
    "carriere, cessible, paturage, metayage, commodat, safer, precaire, autre\n"
    "- bailleur : le propriétaire qui donne à bail\n"
    "- preneur : l'exploitant qui prend à bail\n"
    "- contact_telephone, contact_email : les coordonnées du bailleur\n"
    "- date_debut, date_fin : au format AAAA-MM-JJ\n"
    "- surface_ha : la surface louée en hectares, un nombre\n"
    "- loyer_annuel : le fermage annuel en euros, un nombre\n"
    "- loyer_base_ha : le loyer de base à l'hectare s'il est donné\n"
    "- annee_reference : l'année de référence du loyer de base, un entier\n"
    "- preavis_conge_mois : le préavis de congé en mois, un entier (18 en règle "
    "générale pour un bail rural)\n"
    "- renouvellement_tacite : true ou false\n"
    "- date_revision_fermage : la date anniversaire de révision, AAAA-MM-JJ\n"
    "- taxe_fonciere_part_preneur : le pourcentage de taxe foncière remboursé "
    "par le preneur, un nombre\n"
    "- charges_recuperables : ce que le preneur rembourse, en texte court\n"
    "- references_cadastrales : les parcelles louées (section et numéro)\n"
    "- clauses_environnementales : les clauses environnementales, en texte court\n"
    "- droit_preemption : ce que le bail dit du droit de préemption du preneur"
)

TEXTE = (
    "designation", "type_bail", "bailleur", "preneur", "contact_telephone",
    "contact_email", "charges_recuperables", "references_cadastrales",
    "clauses_environnementales", "droit_preemption",
)
DATES = ("date_debut", "date_fin", "date_revision_fermage")
NOMBRES = ("surface_ha", "loyer_annuel", "loyer_base_ha", "taxe_fonciere_part_preneur")
ENTIERS = ("annee_reference", "preavis_conge_mois")
BOOLEENS = ("renouvellement_tacite",)

CHAMPS = TEXTE + DATES + NOMBRES + ENTIERS + BOOLEENS


def lire(data: bytes, nom_fichier: str) -> dict | None:
    """Les champs lus dans le bail, ou None si rien n'est exploitable."""
    if not llm.is_configured() or not data:
        return None
    mime = _MIME.get(os.path.splitext(nom_fichier)[1].lower())
    if not mime:
        return None
    try:
        brut = llm.extract_json_from_document(data, mime, _PROMPT)
    except Exception:  # noqa: BLE001 — toute erreur IA → repli silencieux
        return None
    if not brut:
        return None
    return {cle: brut.get(cle) for cle in CHAMPS}
