"""Façade LLM multi-fournisseur : bascule Gemini ↔ Mistral.

Le fournisseur actif est choisi par le réglage `AI_PROVIDER` (`gemini` par
défaut, `mistral` pour basculer). Tous les appels IA du projet passent par ce
module ; changer de fournisseur ne demande qu'une variable d'environnement.

Interface identique aux clients sous-jacents :
`is_configured`, `generate_text`, `generate_json`, `extract_json_from_document`,
`stream_text`.
"""

from __future__ import annotations

from django.conf import settings

from . import gemini, mistral


class AINotConfigured(RuntimeError):
    """Levée quand le fournisseur actif n'a pas de clé configurée."""


def provider_name() -> str:
    """Nom normalisé du fournisseur actif (`gemini` ou `mistral`)."""
    return "mistral" if (getattr(settings, "AI_PROVIDER", "") or "gemini").lower() == "mistral" else "gemini"


def _provider():
    return mistral if provider_name() == "mistral" else gemini


def is_configured() -> bool:
    return _provider().is_configured()


def generate_text(messages: list[dict], *, temperature: float = 0.7) -> str:
    return _provider().generate_text(messages, temperature=temperature)


def generate_json(messages: list[dict], *, temperature: float = 0.2) -> dict:
    return _provider().generate_json(messages, temperature=temperature)


def extract_json_from_document(data: bytes, mime_type: str, prompt: str, *, temperature: float = 0.1) -> dict:
    return _provider().extract_json_from_document(data, mime_type, prompt, temperature=temperature)


def stream_text(messages: list[dict], *, temperature: float = 0.7):
    yield from _provider().stream_text(messages, temperature=temperature)
