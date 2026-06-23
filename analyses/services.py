"""Extraction OCR/IA des rapports d'analyse (parité lab.extractTextFromPdf + parsing).

Le texte brut d'un rapport (PDF → texte) est envoyé à Gemini pour en extraire
les valeurs numériques structurées. Repli propre si l'IA n'est pas configurée :
le rapport reste en statut `pending_ocr` sans valeurs inventées.
"""

from __future__ import annotations

from ia import gemini

_TYPE_LABEL = {"soil": "sol", "water": "eau", "leaf": "foliaire", "plant": "plante"}

_PROMPT = (
    "Tu es un expert agronome. Extrais les valeurs numériques d'un rapport de "
    "laboratoire ({label}) en JSON strict. Si une valeur n'est pas trouvée, utilise null. "
    "Pour nitrogenMgKg : si en g/kg, multiplie par 1000. Pour organicMatterPct : matière "
    "organique en %. Pour electricalConductivity : CE en dS/m. "
    'Schéma : {{"ph": null, "organicMatterPct": null, "nitrogenMgKg": null, '
    '"phosphorusMgKg": null, "potassiumMgKg": null, "electricalConductivity": null, '
    '"recommendations": ""}}'
)


def extract_from_text(raw_text: str, analysis_type: str = "soil") -> dict | None:
    """Renvoie les valeurs extraites, ou None si l'IA n'est pas configurée."""
    if not gemini.is_configured() or not raw_text.strip():
        return None
    label = _TYPE_LABEL.get(analysis_type, analysis_type)
    return gemini.generate_json([
        {"role": "system", "content": _PROMPT.format(label=label)},
        {"role": "user", "content": raw_text[:8000]},
    ])


def apply_extraction(report) -> bool:
    """Applique l'extraction IA sur un rapport à partir de son texte OCR. True si appliqué."""
    data = extract_from_text(report.ocr_raw_text, report.analysis_type)
    if not data:
        return False
    report.parsed_data = data
    report.ph = data.get("ph")
    report.organic_matter_pct = data.get("organicMatterPct")
    report.nitrogen_mg_kg = data.get("nitrogenMgKg")
    report.phosphorus_mg_kg = data.get("phosphorusMgKg")
    report.potassium_mg_kg = data.get("potassiumMgKg")
    report.electrical_conductivity = data.get("electricalConductivity")
    report.recommendations = data.get("recommendations", "") or ""
    report.status = report.Status.OCR_DONE
    report.save()
    return True
