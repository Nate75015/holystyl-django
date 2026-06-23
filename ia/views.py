"""Vues web IA : page Assistant + endpoint SSE de streaming."""

import json

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from exploitations.models import Exploitation

from . import gemini, services
from .models import AiConversation


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def assistant(request):
    exploitation = _exploitation(request)
    history = (
        AiConversation.objects.filter(exploitation=exploitation).order_by("created_at")[:50]
        if exploitation else []
    )
    return render(
        request,
        "ia/assistant.html",
        {"history": history, "ai_ready": gemini.is_configured(), "page_title": _("Assistant IA")},
    )


@login_required
@require_GET
def stream(request):
    """SSE : réponse de l'assistant en flux (EventSource). Parité /api/ai/stream."""
    message = request.GET.get("message", "").strip()
    exploitation = _exploitation(request)

    def event_stream():
        if not message:
            yield "event: error\ndata: message vide\n\n"
            return
        AiConversation.objects.create(exploitation=exploitation, user=request.user, role="user", content=message)

        if not gemini.is_configured():
            payload = json.dumps({"text": services.ASSISTANT_NOT_CONFIGURED})
            yield f"data: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
            AiConversation.objects.create(
                exploitation=exploitation, user=request.user, role="assistant",
                content=services.ASSISTANT_NOT_CONFIGURED,
            )
            return

        ctx = services.build_context(exploitation)
        messages = [
            {"role": "system", "content": f"Tu es l'assistant Holystyl. Parcelles : {ctx['parcelles']}."},
            {"role": "user", "content": message},
        ]
        full = []
        for chunk in gemini.stream_text(messages):
            full.append(chunk)
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "event: done\ndata: {}\n\n"
        AiConversation.objects.create(
            exploitation=exploitation, user=request.user, role="assistant", content="".join(full)
        )

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
