"""Extraction OCR/IA des analyses de sol depuis un document (PDF/image) via Gemini.

Repli propre : si Gemini n'est pas configuré (pas de GEMINI_API_KEY) ou si le
type de fichier n'est pas exploitable, renvoie None — l'analyse est alors
enregistrée avec le seul document, sans valeurs inventées.
"""

from __future__ import annotations

import os

from ia import gemini

_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_PROMPT = (
    "Tu es un expert agronome. Lis ce rapport d'analyse de sol (type AUREA, LCA…) "
    "et extrais les valeurs en JSON strict, une clé par mesure. Mets null si une "
    "valeur est absente. Pour les nombres, renvoie un nombre (point décimal), sans "
    "unité ni symbole. EXCEPTIONS gardées en texte : taux_saturation, somme_16_hap, "
    "somme_7_pcb (conserve « <0.056 », « >100 »…) ; les dates au format AAAA-MM-JJ. "
    "Clés attendues : "
    "laboratoire (nom du labo), numero_laboratoire, reference, technicien, commune, "
    "profondeur_prelevement, date_prelevement, date_arrivee_labo, date_expedition, "
    "ph (pH eau), ph_kcl, ec (conductivité mS/cm), calcaire_total (%), "
    "calcaire_actif (% sec), calcium_cao (mg/kg), matiere_organique (%), "
    "carbone_organique (%), azote_total (N %), c_n (rapport C/N), coefficient_k2 (%), "
    "azote_ammoniacal (N-NH4 mg/kg), phosphore_assimilable (P2O5 mg/kg), "
    "phosphore_olsen (mg/kg), potassium_echangeable (K2O mg/kg), magnesium_mgo (mg/kg), "
    "sodium_na2o (mg/kg), bore (B mg/kg), cuivre (Cu EDTA mg/kg), fer (Fe EDTA mg/kg), "
    "manganese (Mn EDTA mg/kg), zinc (Zn EDTA mg/kg), cec (meq/100g), taux_saturation, "
    "ca_cec (%), k_cec (%), mg_cec (%), na_cec (%), h_cec (%), type_sol, argile (%), "
    "limons_fins (%), limons_grossiers (%), sables_fins (%), sables_grossiers (%), "
    "humidite (sur brut %), matiere_seche (sur brut %), refus_2mm (%), "
    "densite_apparente (g/cm3), reserve_utile (RU mm/cm), "
    "reserve_facilement_utilisable (RFU mm/cm), capacite_retention_pf25 (% MS), "
    "capacite_retention_pf42 (% MS), indice_battance, risque_battance (texte), "
    "cadmium, chrome, cuivre_total, mercure, nickel, plomb, zinc_total, arsenic, "
    "cobalt, molybdene, selenium, fer_total (% sec), manganese_total, bore_total, "
    "aluminium_echangeable, aluminium_total (% sec), somme_16_hap, somme_7_pcb."
)

# Champs texte (non convertis en float) et dates (parsées en AAAA-MM-JJ) côté vue.
TEXT_FIELDS = (
    "laboratoire", "numero_laboratoire", "reference", "technicien", "commune",
    "profondeur_prelevement", "type_sol", "risque_battance", "taux_saturation",
    "somme_16_hap", "somme_7_pcb",
)
DATE_FIELDS = ("date_prelevement", "date_arrivee_labo", "date_expedition")

_NUMERIC_FIELDS = (
    "ph", "ph_kcl", "ec", "calcaire_total", "calcaire_actif", "calcium_cao",
    "matiere_organique", "carbone_organique", "azote_total", "c_n", "coefficient_k2",
    "azote_ammoniacal", "phosphore_assimilable", "phosphore_olsen",
    "potassium_echangeable", "magnesium_mgo", "sodium_na2o", "bore", "cuivre", "fer",
    "manganese", "zinc", "cec", "ca_cec", "k_cec", "mg_cec", "na_cec", "h_cec",
    "argile", "limons_fins", "limons_grossiers", "sables_fins", "sables_grossiers",
    "humidite", "matiere_seche", "refus_2mm", "densite_apparente", "reserve_utile",
    "reserve_facilement_utilisable", "capacite_retention_pf25", "capacite_retention_pf42",
    "indice_battance", "cadmium", "chrome", "cuivre_total", "mercure", "nickel",
    "plomb", "zinc_total", "arsenic", "cobalt", "molybdene", "selenium", "fer_total",
    "manganese_total", "bore_total", "aluminium_echangeable", "aluminium_total",
)

_FIELDS = TEXT_FIELDS + DATE_FIELDS + _NUMERIC_FIELDS


def extract_soil_analysis(data: bytes, filename: str) -> dict | None:
    """Renvoie les valeurs extraites du document, ou None si non exploitable/IA absente."""
    if not gemini.is_configured() or not data:
        return None
    mime = _MIME.get(os.path.splitext(filename)[1].lower())
    if not mime:
        return None  # type non géré par l'OCR multimodal (csv, xls…)
    try:
        raw = gemini.extract_json_from_document(data, mime, _PROMPT)
    except Exception:  # noqa: BLE001 — toute erreur IA → repli silencieux
        return None
    return {k: raw.get(k) for k in _FIELDS} if raw else None
