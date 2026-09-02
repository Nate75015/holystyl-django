"""Vues publiques : landing SEO, lead magnet, chat Alex."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import alex_chat, capture_lead


def home(request):
    """Landing publique (SEO). Redirige vers le cockpit si déjà connecté."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "public/home.html", {"page_title": "Isidor — Irrigation de précision"})


@require_POST
def lead_capture(request):
    email = request.POST.get("email", "").strip()
    if email:
        capture_lead(email, source=request.POST.get("source", "guide_analyses"))
        messages.success(request, _("Merci ! Votre guide arrive par email."))
    return redirect("public:home")


@csrf_exempt
@require_POST
def alex(request):
    """Endpoint chat de l'agent commercial Alex (public)."""
    import json

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    answer = alex_chat(payload.get("messages", []))
    return JsonResponse({"response": answer})
