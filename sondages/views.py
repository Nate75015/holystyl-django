"""Vues Sondages : liste, création, détail/vote, résultats, clôture."""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .models import Choix, Sondage, Vote


def _user_exploitations(user):
    return Exploitation.objects.filter(Q(owner=user) | Q(team_members__user=user)).distinct()


def _visible_sondages(user):
    expl_ids = list(_user_exploitations(user).values_list("id", flat=True))
    # Sondages de ses exploitations + ceux qu'il a créés (sans exploitation)
    return Sondage.objects.filter(Q(exploitation_id__in=expl_ids) | Q(created_by=user)).distinct()


@login_required
def liste(request):
    sondages = list(_visible_sondages(request.user).prefetch_related("choix", "votes"))
    for s in sondages:
        s.nb_votes = s.total_votes()
        s.a_vote = s.user_vote(request.user) is not None
    return render(request, "sondages/liste.html", {"sondages": sondages, "page_title": _("Sondages")})


@login_required
def create(request):
    if request.method == "POST":
        question = (request.POST.get("question") or "").strip()
        choix_list = [c.strip() for c in request.POST.getlist("choix") if c.strip()]
        errors = []
        if not question:
            errors.append(_("La question est obligatoire."))
        if len(choix_list) < 2:
            errors.append(_("Proposez au moins deux choix."))
        if errors:
            return render(request, "sondages/create.html", {
                "errors": errors, "page_title": _("Nouveau sondage"),
                "form": {"question": question, "choix": choix_list or ["", ""]},
            })

        sondage = Sondage.objects.create(
            question=question, created_by=request.user,
            exploitation=_user_exploitations(request.user).first(),
        )
        for i, texte in enumerate(choix_list):
            Choix.objects.create(sondage=sondage, texte=texte, ordre=i)
        return redirect("sondages:detail", pk=sondage.pk)

    return render(request, "sondages/create.html", {
        "page_title": _("Nouveau sondage"), "form": {"question": "", "choix": ["", ""]},
    })


@login_required
def detail(request, pk):
    sondage = get_object_or_404(_visible_sondages(request.user), pk=pk)
    mon_choix = sondage.user_vote(request.user)
    show_results = mon_choix is not None or sondage.closed or sondage.created_by_id == request.user.id
    return render(request, "sondages/detail.html", {
        "sondage": sondage,
        "mon_choix": mon_choix,
        "show_results": show_results,
        "results": sondage.results(),
        "page_title": sondage.question,
    })


@login_required
@require_POST
def vote(request, pk):
    sondage = get_object_or_404(_visible_sondages(request.user), pk=pk)
    if sondage.closed or sondage.user_vote(request.user) is not None:
        return redirect("sondages:detail", pk=sondage.pk)
    choix = get_object_or_404(Choix, pk=request.POST.get("choix"), sondage=sondage)
    Vote.objects.get_or_create(sondage=sondage, user=request.user, defaults={"choix": choix})
    return redirect("sondages:detail", pk=sondage.pk)


@login_required
@require_POST
def cloturer(request, pk):
    sondage = get_object_or_404(Sondage, pk=pk, created_by=request.user)
    sondage.closed = not sondage.closed
    sondage.save(update_fields=["closed", "updated_at"])
    return redirect("sondages:detail", pk=sondage.pk)
