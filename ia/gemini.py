"""Client Google Gemini (SDK `google-genai`).

Remplace le proxy Manus Forge (Gemini 2.5 Flash). Conçu pour rester inerte
si aucune clé n'est configurée : `is_configured()` renvoie False et les
services renvoient alors un message explicite plutôt que d'inventer une
réponse. L'import du SDK est paresseux pour ne pas exiger sa présence.
"""

from __future__ import annotations

import json

from django.conf import settings


class AINotConfigured(RuntimeError):
    """Levée quand l'IA est appelée sans clé Gemini configurée."""


def is_configured() -> bool:
    return bool(getattr(settings, "GEMINI_API_KEY", ""))


def _client():
    if not is_configured():
        raise AINotConfigured("GEMINI_API_KEY manquant — assistant IA non configuré.")
    from google import genai  # import paresseux

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _to_contents(messages: list[dict]) -> tuple[str | None, str]:
    """Sépare l'éventuel message system et concatène le reste en prompt simple."""
    system = None
    parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            system = content
        else:
            prefix = "Utilisateur" if role == "user" else "Assistant"
            parts.append(f"{prefix}: {content}")
    return system, "\n".join(parts)


def generate_text(messages: list[dict], *, temperature: float = 0.7) -> str:
    system, prompt = _to_contents(messages)
    from google.genai import types

    client = _client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
    )
    return resp.text or ""


def generate_json(messages: list[dict], *, temperature: float = 0.2) -> dict:
    """Force une réponse JSON (utilisé pour l'extraction d'intentions)."""
    system, prompt = _to_contents(messages)
    from google.genai import types

    client = _client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    try:
        return json.loads(resp.text or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_json_from_document(data: bytes, mime_type: str, prompt: str, *, temperature: float = 0.1) -> dict:
    """Envoie un document (PDF/image) à Gemini (multimodal) et force une réponse JSON."""
    from google.genai import types

    client = _client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), prompt],
        config=types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json"),
    )
    try:
        return json.loads(resp.text or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def stream_text(messages: list[dict], *, temperature: float = 0.7):
    """Génère la réponse en flux (chunks de texte) pour le SSE."""
    system, prompt = _to_contents(messages)
    from google.genai import types

    client = _client()
    for chunk in client.models.generate_content_stream(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
    ):
        if getattr(chunk, "text", None):
            yield chunk.text
