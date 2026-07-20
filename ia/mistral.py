"""Client Mistral AI (SDK `mistralai`) — interface identique à `ia.gemini`.

Fournisseur LLM alternatif, sélectionnable via `AI_PROVIDER=mistral`. Conçu
pour rester inerte sans clé : `is_configured()` renvoie False. L'import du SDK
est paresseux pour ne pas exiger sa présence quand Gemini est utilisé.
"""

from __future__ import annotations

import base64
import json

from django.conf import settings


class AINotConfigured(RuntimeError):
    """Levée quand Mistral est appelé sans clé configurée."""


def is_configured() -> bool:
    return bool(getattr(settings, "MISTRAL_API_KEY", ""))


def _client():
    if not is_configured():
        raise AINotConfigured("MISTRAL_API_KEY manquant — assistant IA non configuré.")
    from mistralai import Mistral  # import paresseux

    return Mistral(api_key=settings.MISTRAL_API_KEY)


def _model() -> str:
    return getattr(settings, "MISTRAL_MODEL", "mistral-small-latest")


def _content(resp) -> str:
    """Texte de la première réponse (tolérant aux réponses vides)."""
    if getattr(resp, "choices", None):
        return resp.choices[0].message.content or ""
    return ""


def generate_text(messages: list[dict], *, temperature: float = 0.7) -> str:
    client = _client()
    resp = client.chat.complete(model=_model(), messages=messages, temperature=temperature)
    return _content(resp)


def generate_json(messages: list[dict], *, temperature: float = 0.2) -> dict:
    """Force une réponse JSON (extraction d'intentions)."""
    client = _client()
    resp = client.chat.complete(
        model=_model(),
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(_content(resp) or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_json_from_document(data: bytes, mime_type: str, prompt: str, *, temperature: float = 0.1) -> dict:
    """Envoie un document (PDF/image) à Mistral (multimodal) et force du JSON."""
    client = _client()
    data_uri = f"data:{mime_type};base64,{base64.b64encode(data).decode()}"
    if mime_type == "application/pdf":
        doc = {"type": "document_url", "document_url": data_uri}
    else:
        doc = {"type": "image_url", "image_url": data_uri}
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, doc]}]
    try:
        resp = client.chat.complete(
            model=_model(),
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(_content(resp) or "{}")
    except Exception:  # noqa: BLE001 — document non supporté / réseau : on reste inerte
        return {}


def stream_text(messages: list[dict], *, temperature: float = 0.7):
    """Génère la réponse en flux (chunks de texte) pour le SSE."""
    client = _client()
    for event in client.chat.stream(model=_model(), messages=messages, temperature=temperature):
        try:
            delta = event.data.choices[0].delta.content
        except (AttributeError, IndexError, TypeError):
            delta = None
        if delta:
            yield delta
