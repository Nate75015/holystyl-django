"""Vues publiques : landing SEO, lead magnet, chat Alex."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from exploitations import geo
from exploitations.models import Exploitation

from .services import alex_chat, capture_lead


def home(request):
    """Landing publique (SEO). Redirige vers le cockpit si déjà connecté."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "public/home.html", {"page_title": "Isidor — Irrigation de précision"})


def terroirs(request):
    """« Nos terroirs » : la vitrine des producteurs de la place de marché.

    La vente elle-même reste dans `vente` — boutiques, panier, commandes.
    Cette page est la porte d'entrée : elle montre qui vend, et renvoie vers
    les boutiques et le catalogue.

    Le filtre porte sur `annuaire_public`, pas sur l'ensemble des comptes :
    le nom et la commune d'un exploitant ne se publient pas sans son accord.

    Le tri et les filtres se font ensuite dans la page, sans aller-retour :
    l'annuaire est court, et une recherche qui attend le réseau n'est pas une
    recherche instantanée.
    """
    fermes = list(
        Exploitation.objects.filter(annuaire_public=True)
        .select_related("boutique")
        .prefetch_related("adresses")
        .order_by("city", "name")
    )

    # La commune et le code postal se lisent sur l'adresse principale, pas sur
    # les champs de l'exploitation : ceux-ci n'en sont qu'un miroir, recopié
    # par `appliquer_adresse_principale()`, et un miroir peut avoir divergé.
    # Département et région se déduisent ensuite du code postal, jamais saisis.
    for f in fermes:
        adresses = list(f.adresses.all())
        principale = next((a for a in adresses if a.principale), None)
        if principale is None and adresses:
            principale = adresses[0]
        f.ville = (getattr(principale, "city", "") or f.city or "").strip()
        f.cp = (getattr(principale, "postal_code", "") or f.postal_code or "").strip()
        f.dep_code, f.dep_nom, f.region = geo.situer(f.cp)

    return render(request, "public/terroirs.html", {
        "fermes": fermes,
        "nb": len(fermes),
        "referentiel": geo.referentiel(),
        "layout_nu": True,
        "page_vitrine": "terroirs",
        "page_title": _("Nos terroirs"),
    })


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
