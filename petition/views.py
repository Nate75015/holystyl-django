"""Vues Pétitions : liste, création, détail/signature, clôture, reformulation IA."""

import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from ia import llm

from .models import Petition, Signature


def _user_exploitations(user):
    return Exploitation.objects.filter(Q(owner=user) | Q(team_members__user=user)).distinct()


def _creator_info(user):
    """Nom + prénom (depuis la section Identité de l'exploitation) + email du créateur."""
    if user is None:
        return None
    exp = Exploitation.objects.filter(owner=user).first()
    nom = (exp.name if exp and exp.name else "").strip()
    prenom = (exp.prenom if exp and exp.prenom else "").strip()
    complet = " ".join(filter(None, [prenom, nom])) or user.display_name
    base = complet or user.email
    return {
        "nom": nom, "prenom": prenom, "email": user.email,
        "complet": complet, "initiale": base[:1].upper(),
    }


def _visible_petitions(user):
    expl_ids = list(_user_exploitations(user).values_list("id", flat=True))
    # Pétitions de ses exploitations + celles qu'il a créées (sans exploitation)
    return Petition.objects.filter(Q(exploitation_id__in=expl_ids) | Q(created_by=user)).distinct()


@login_required
def liste(request):
    petitions = list(_visible_petitions(request.user).prefetch_related("signatures").select_related("created_by"))
    for p in petitions:
        p.nb_signatures = p.signature_count()
        p.a_signe = p.user_signed(request.user)
        p.creator = _creator_info(p.created_by)
    return render(request, "petition/liste.html", {"petitions": petitions, "page_title": _("Pétitions")})


@login_required
def create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        goal_raw = (request.POST.get("goal") or "").strip()
        goal = int(goal_raw) if goal_raw.isdigit() else 0

        errors = []
        if not title:
            errors.append(_("Le titre est obligatoire."))
        if errors:
            return render(request, "petition/create.html", {
                "errors": errors, "page_title": _("Nouvelle pétition"),
                "form": {"title": title, "description": description, "goal": goal_raw},
            })

        petition = Petition.objects.create(
            title=title, description=description, goal=goal,
            created_by=request.user,
            exploitation=_user_exploitations(request.user).first(),
        )
        return redirect("petition:detail", pk=petition.pk)

    return render(request, "petition/create.html", {
        "page_title": _("Nouvelle pétition"),
        "form": {"title": "", "description": "", "goal": ""},
    })


@login_required
def detail(request, pk):
    petition = get_object_or_404(_visible_petitions(request.user), pk=pk)
    return render(request, "petition/detail.html", {
        "petition": petition,
        "creator": _creator_info(petition.created_by),
        "a_signe": petition.user_signed(request.user),
        "signatures": petition.signatures.select_related("user")[:50],
        "page_title": petition.title,
    })


@login_required
@require_POST
def signer(request, pk):
    petition = get_object_or_404(_visible_petitions(request.user), pk=pk)
    if not petition.closed:
        comment = (request.POST.get("comment") or "").strip()[:280]
        Signature.objects.get_or_create(
            petition=petition, user=request.user, defaults={"comment": comment},
        )
    return redirect("petition:detail", pk=petition.pk)


@login_required
@require_POST
def reformuler(request):
    """Reformule un titre ou une description de pétition via l'IA (JSON)."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    field = payload.get("field", "description")
    text = (payload.get("text") or "").strip()

    if not text:
        return JsonResponse({"error": _("Rien à reformuler : le champ est vide.")}, status=400)
    if not llm.is_configured():
        return JsonResponse({"error": _("Assistant IA non configuré (clé Gemini manquante).")}, status=503)

    if field == "title":
        instruction = _(
            "Reformule ce titre de pétition en une seule ligne, claire, percutante et "
            "mobilisatrice. Réponds uniquement par le titre, sans guillemets ni préambule."
        )
    else:
        instruction = _(
            "Reformule ce texte de pétition en français : plus clair, structuré et "
            "engageant, tout en restant factuel et respectueux. Garde une longueur "
            "similaire. Réponds uniquement par le texte reformulé, sans préambule."
        )

    system = _(
        "Tu es un assistant qui aide des agriculteurs à rédiger des pétitions. "
        "Tu écris dans un français clair et professionnel."
    )
    try:
        out = llm.generate_text(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"{instruction}\n\n---\n{text}"},
            ],
            temperature=0.7,
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"text": (out or "").strip().strip('"')})


@login_required
@require_POST
def cloturer(request, pk):
    petition = get_object_or_404(Petition, pk=pk, created_by=request.user)
    petition.closed = not petition.closed
    petition.save(update_fields=["closed", "updated_at"])
    return redirect("petition:detail", pk=petition.pk)


@login_required
def edit(request, pk):
    """Modifie une pétition (créateur uniquement)."""
    petition = get_object_or_404(Petition, pk=pk, created_by=request.user)
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        goal_raw = (request.POST.get("goal") or "").strip()
        errors = []
        if not title:
            errors.append(_("Le titre est obligatoire."))
        if errors:
            return render(request, "petition/edit.html", {
                "errors": errors, "petition": petition, "page_title": _("Modifier la pétition"),
                "form": {"title": title, "description": description, "goal": goal_raw},
            })
        petition.title = title
        petition.description = description
        petition.goal = int(goal_raw) if goal_raw.isdigit() else 0
        petition.save(update_fields=["title", "description", "goal", "updated_at"])
        return redirect("petition:detail", pk=petition.pk)

    return render(request, "petition/edit.html", {
        "petition": petition,
        "form": {"title": petition.title, "description": petition.description,
                 "goal": petition.goal or ""},
        "page_title": _("Modifier la pétition"),
    })


@login_required
@require_POST
def delete(request, pk):
    """Supprime une pétition (créateur uniquement)."""
    petition = get_object_or_404(Petition, pk=pk, created_by=request.user)
    petition.delete()
    return redirect("petition:liste")
