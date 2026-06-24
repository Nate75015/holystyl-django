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
    "Tu es un expert agronome. Lis ce rapport d'analyse de sol et extrais les "
    "valeurs en JSON strict. Mets null si une valeur est absente. "
    "Schéma : {"
    '"laboratoire": null, '          # nom du laboratoire
    '"ph": null, '                   # pH (eau)
    '"ec": null, '                   # conductivité électrique (mS/cm)
    '"azote_total": null, '          # azote total
    '"phosphore_assimilable": null, '  # P assimilable
    '"potassium_echangeable": null, '  # K échangeable
    '"matiere_organique": null, '    # matière organique en %
    '"calcaire_total": null'         # calcaire total
    "}"
)

_FIELDS = (
    "laboratoire", "ph", "ec", "azote_total", "phosphore_assimilable",
    "potassium_echangeable", "matiere_organique", "calcaire_total",
)


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
