"""Vues web Réseau : demandes de connexion, acceptation, réseau (type LinkedIn)."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from notifications.services import notify

from .models import Connexion

User = get_user_model()


def _notify_demande(demandeur, destinataire):
    """Notifie le destinataire d'une nouvelle demande d'adhésion."""
    from django.urls import reverse

    notify(
        destinataire,
        type="reseau",
        title=_("Nouvelle demande d'adhésion"),
        message=_("%(nom)s souhaite rejoindre votre réseau.") % {"nom": demandeur.display_name},
        action_url=reverse("reseaux:reseaux"),
    )


def _person(u, with_exploitation=False):
    data = {"id": u.id, "nom": u.display_name, "email": u.email,
            "initiale": (u.display_name or u.email or "?")[:1].upper()}
    if with_exploitation:
        exp = u.exploitations.all()[0] if u.exploitations.all() else None
        data.update({
            "exploitation": exp.name if exp else "",
            "lieu": (exp.city if exp and exp.city else ""),
            "cultures": (exp.productions if exp and exp.productions else ""),
            "ca": (exp.chiffre_affaires if exp and exp.chiffre_affaires is not None else None),
            "surface": (exp.total_area if exp and exp.total_area is not None else None),
        })
    return data


@login_required
def reseaux(request):
    me = request.user
    accepted = Connexion.objects.filter(statut=Connexion.Statut.ACCEPTEE).filter(
        Q(demandeur=me) | Q(destinataire=me)
    ).select_related("demandeur", "destinataire")
    recues = Connexion.objects.filter(destinataire=me, statut=Connexion.Statut.EN_ATTENTE).select_related("demandeur")
    envoyees = Connexion.objects.filter(demandeur=me, statut=Connexion.Statut.EN_ATTENTE).select_related("destinataire")

    reseau = []
    for c in accepted:
        other = c.destinataire if c.demandeur_id == me.id else c.demandeur
        reseau.append({"cid": c.id, **_person(other)})

    # Personnes à découvrir : agriculteurs actifs sans lien existant avec moi.
    known = {me.id}
    for c in Connexion.objects.filter(Q(demandeur=me) | Q(destinataire=me)).values_list("demandeur_id", "destinataire_id"):
        known.update(c)
    candidats = (
        User.objects.filter(is_active=True, is_staff=False)
        .exclude(id__in=known)
        .prefetch_related("exploitations")
        .order_by("full_name", "email")
    )
    suggestions = [_person(u, with_exploitation=True) for u in candidats]

    return render(request, "reseaux/reseaux.html", {
        "reseau": reseau,
        "recues": [{"cid": c.id, "message": c.message, **_person(c.demandeur)} for c in recues],
        "envoyees": [{"cid": c.id, **_person(c.destinataire)} for c in envoyees],
        "suggestions": suggestions,
        "kpi_reseau": len(reseau),
        "kpi_recues": recues.count(),
        "kpi_envoyees": envoyees.count(),
        "page_title": _("Réseau"),
    })


@login_required
@require_POST
def demander(request, user_id):
    """Envoie une demande de connexion à un utilisateur."""
    me = request.user
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other.pk != me.pk:
        existing = Connexion.between(me, other)
        if existing is None:
            Connexion.objects.create(
                demandeur=me, destinataire=other,
                message=(request.POST.get("message") or "").strip()[:280],
            )
            _notify_demande(me, other)
            messages.success(request, _("Demande de connexion envoyée."))
        elif existing.statut == Connexion.Statut.REFUSEE and existing.demandeur_id == me.id:
            # Renouvelle une demande précédemment refusée.
            existing.statut = Connexion.Statut.EN_ATTENTE
            existing.responded_at = None
            existing.save(update_fields=["statut", "responded_at"])
            _notify_demande(me, other)
            messages.success(request, _("Demande de connexion envoyée."))
    return redirect("reseaux:reseaux")


@login_required
@require_POST
def accepter(request, pk):
    c = get_object_or_404(Connexion, pk=pk, destinataire=request.user, statut=Connexion.Statut.EN_ATTENTE)
    c.statut = Connexion.Statut.ACCEPTEE
    c.responded_at = timezone.now()
    c.save(update_fields=["statut", "responded_at"])
    messages.success(request, _("Vous êtes désormais connectés."))
    return redirect("reseaux:reseaux")


@login_required
@require_POST
def refuser(request, pk):
    c = get_object_or_404(Connexion, pk=pk, destinataire=request.user, statut=Connexion.Statut.EN_ATTENTE)
    c.statut = Connexion.Statut.REFUSEE
    c.responded_at = timezone.now()
    c.save(update_fields=["statut", "responded_at"])
    return redirect("reseaux:reseaux")


@login_required
@require_POST
def retirer(request, pk):
    """Retire une connexion (ou annule une demande envoyée) me concernant."""
    c = get_object_or_404(Connexion, Q(demandeur=request.user) | Q(destinataire=request.user), pk=pk)
    c.delete()
    return redirect("reseaux:reseaux")
