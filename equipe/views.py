"""Vues web équipe : équipe, tâches, mes-tâches (technicien), partage géoloc public."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import Task, TeamMember


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def equipe(request):
    exploitation = _exploitation(request)
    members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()
    return render(request, "equipe/equipe.html", {"members": members, "page_title": _("Équipe")})


@login_required
def taches(request):
    exploitation = _exploitation(request)
    tasks = Task.objects.filter(exploitation=exploitation) if exploitation else Task.objects.none()
    return render(request, "equipe/taches.html", {"tasks": tasks, "page_title": _("Tâches")})


@login_required
def mes_taches(request):
    """Vue technicien : tâches assignées au membre lié à l'utilisateur courant."""
    exploitation = _exploitation(request)
    member = TeamMember.objects.filter(exploitation=exploitation, user=request.user).first()
    tasks = Task.objects.filter(assigned_to=member) if member else Task.objects.none()
    return render(request, "equipe/mes_taches.html", {"tasks": tasks, "page_title": _("Mes tâches")})


def location_share(request, token):
    """Page publique de partage de position (lien 24h)."""
    member = TeamMember.objects.filter(
        location_token=token, location_token_expires_at__gt=timezone.now()
    ).first()
    return render(request, "equipe/location_share.html", {"member": member, "token": token})
