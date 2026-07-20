"""Vues web IA : page Assistant + endpoint SSE de streaming."""

import json
import uuid

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from exploitations.models import Exploitation

from . import llm, services
from .models import AiConversation


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def assistant(request):
    exploitation = _exploitation(request)
    history, current_thread, conversations = [], "", []
    if exploitation:
        # Liste des conversations passées (un thread = une conversation)
        threads = (
            AiConversation.objects.filter(exploitation=exploitation, thread__isnull=False)
            .values("thread").annotate(last=Max("created_at")).order_by("-last")[:40]
        )
        for t in threads:
            title = (
                AiConversation.objects.filter(exploitation=exploitation, thread=t["thread"], role="user")
                .order_by("created_at").values_list("content", flat=True).first()
            )
            conversations.append({
                "thread": str(t["thread"]),
                "title": (title or _("Conversation")).strip()[:60],
                "last": t["last"],
            })

        # Conversation affichée : ?thread=… sinon la plus récente (sauf ?new)
        req_thread = _thread_uuid(request.GET.get("thread"))
        if "new" in request.GET:
            pass  # écran d'accueil, nouvelle conversation
        elif req_thread is not None:
            current_thread = str(req_thread)
            history = AiConversation.objects.filter(
                exploitation=exploitation, thread=req_thread
            ).order_by("created_at")[:100]
        else:
            last = AiConversation.objects.filter(exploitation=exploitation).order_by("-created_at").first()
            if last is not None:
                current_thread = str(last.thread) if last.thread else ""
                qs = AiConversation.objects.filter(exploitation=exploitation)
                qs = qs.filter(thread=last.thread) if last.thread else qs.filter(thread__isnull=True)
                history = qs.order_by("created_at")[:100]
    return render(
        request,
        "ia/assistant.html",
        {
            "history": history,
            "current_thread": current_thread,
            "conversations": conversations,
            "ai_ready": llm.is_configured(),
            "page_title": _("Eric"),
        },
    )


def _thread_uuid(value):
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


@login_required
@require_GET
def stream(request):
    """SSE : réponse de l'assistant en flux (EventSource). Parité /api/ai/stream."""
    message = request.GET.get("message", "").strip()
    thread = _thread_uuid(request.GET.get("thread"))
    exploitation = _exploitation(request)

    def event_stream():
        if not message:
            yield "event: error\ndata: message vide\n\n"
            return
        AiConversation.objects.create(
            exploitation=exploitation, user=request.user, role="user", content=message, thread=thread
        )

        if not llm.is_configured():
            payload = json.dumps({"text": services.ASSISTANT_NOT_CONFIGURED})
            yield f"data: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
            AiConversation.objects.create(
                exploitation=exploitation, user=request.user, role="assistant",
                content=services.ASSISTANT_NOT_CONFIGURED, thread=thread,
            )
            return

        ctx = services.build_context(exploitation)
        messages = [
            {"role": "system", "content": f"Tu es Eric, le conseiller agronome de Holystyl (irrigation de précision). Réponds en français, de façon concise et pratique. Contexte parcelles : {ctx['parcelles']}."},
            {"role": "user", "content": message},
        ]
        full = []
        try:
            for chunk in llm.stream_text(messages):
                full.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception:  # noqa: BLE001 — erreur/indispo IA (ex: 503) → message propre
            if not full:
                msg = "Désolé, le service IA est momentanément indisponible. Réessaie dans un instant."
                full.append(msg)
                yield f"data: {json.dumps({'text': msg})}\n\n"
        yield "event: done\ndata: {}\n\n"
        AiConversation.objects.create(
            exploitation=exploitation, user=request.user, role="assistant", content="".join(full), thread=thread
        )

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
