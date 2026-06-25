"""Vues web équipe : équipe, tâches, mes-tâches (technicien), partage géoloc public."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .forms import TeamMemberForm
from .models import Task, TeamMember


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def equipe(request):
    exploitation = _exploitation(request)
    form = TeamMemberForm()
    if request.method == "POST":
        if exploitation is None:
            messages.error(request, _("Créez d'abord votre exploitation avant d'ajouter un membre."))
        else:
            form = TeamMemberForm(request.POST)
            if form.is_valid():
                member = form.save(exploitation=exploitation, managed_by=request.user)
                messages.success(request, _("%(name)s a été ajouté à l'équipe.") % {"name": member.name})
                return redirect("equipe:equipe")
    members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()
    return render(request, "equipe/equipe.html", {"members": members, "form": form, "page_title": _("Équipe")})


@login_required
def membre_edit(request, pk):
    exploitation = _exploitation(request)
    member = get_object_or_404(TeamMember, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = TeamMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, _("%(name)s a été mis à jour.") % {"name": member.name})
            return redirect("equipe:equipe")
    else:
        form = TeamMemberForm(instance=member)
    return render(request, "equipe/edit.html", {"form": form, "member": member, "page_title": _("Modifier le membre")})


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
