"""Vues publiques : landing SEO, lead magnet, activation, chat Alex."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.services import activate_code
from exploitations.models import Exploitation

from .services import alex_chat, capture_lead


def home(request):
    """Landing publique (SEO). Redirige vers le cockpit si déjà connecté."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "public/home.html", {"page_title": "Holystyl — Irrigation de précision"})


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


@login_required
def activer(request):
    """Page d'activation : saisie d'un code post-paiement."""
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        exploitation = Exploitation.objects.filter(owner=request.user).first()
        if activate_code(code, request.user, exploitation):
            messages.success(request, _("Votre accès Holystyl est activé !"))
            return redirect("core:dashboard")
        messages.error(request, _("Code invalide ou déjà utilisé."))
    return render(request, "public/activer.html", {"page_title": _("Activer mon compte")})
