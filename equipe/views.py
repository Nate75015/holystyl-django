"""Vues web équipe : équipe, tâches, mes-tâches (technicien), partage géoloc public."""

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core import espaces as espaces_service
from core.decorators import espace_requis
from core.espaces import EMPLOYE, EXPLOITANT
from exploitations.models import Exploitation

from . import invitations
from .forms import InvitationAccountForm, TaskForm, TeamMemberForm
from .models import Task, TeamMember

User = get_user_model()


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
@espace_requis(EXPLOITANT)
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
    return render(request, "equipe/equipe.html", {
        "members": members, "form": form, "roles": TeamMember.Role.choices, "page_title": _("Équipe"),
    })


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
@require_POST
def membre_inviter(request, pk):
    """Envoie au membre le lien qui lui ouvrira son espace employé."""
    exploitation = _exploitation(request)
    member = get_object_or_404(TeamMember, pk=pk, exploitation=exploitation)
    if member.user_id is not None:
        messages.info(request, _("%(name)s a déjà un compte lié.") % {"name": member.name})
    elif not member.email:
        messages.error(request, _("Renseignez un email avant d'inviter %(name)s.") % {"name": member.name})
    else:
        try:
            invitations.envoyer(member, request)
        except (BadHeaderError, OSError):
            # SMTP indisponible ou refusé : le dire, ne pas laisser croire à un envoi.
            messages.error(request, _("L'invitation n'a pas pu être envoyée à %(email)s. "
                                      "Réessayez dans un instant.") % {"email": member.email})
        else:
            messages.success(request, _("Invitation envoyée à %(email)s.") % {"email": member.email})
    return redirect("equipe:membre_edit", pk=member.pk)


def invitation(request, token):
    """Acceptation d'une invitation — publique, le jeton fait l'authentification.

    Quatre situations, une seule page : lien mort, compte à créer, compte
    existant à connecter, ou compte déjà connecté à confirmer.
    """
    member = invitations.membre_du_jeton(token)
    if member is None:
        return render(request, "equipe/invitation.html",
                      {"etat": "invalide", "page_title": _("Invitation")}, status=410)

    if member.user_id is not None:
        if request.user.is_authenticated and request.user.pk == member.user_id:
            return redirect("core:dashboard")
        return render(request, "equipe/invitation.html",
                      {"etat": "deja_utilisee", "membre": member, "page_title": _("Invitation")},
                      status=410)

    if request.user.is_authenticated:
        etat = "confirmer"
        form = None
    elif User.objects.filter(email__iexact=member.email).exists():
        etat = "connexion"
        form = None
    else:
        etat = "creation"
        form = InvitationAccountForm(email=member.email)

    if request.method == "POST" and etat in ("confirmer", "creation"):
        user = request.user
        if etat == "creation":
            form = InvitationAccountForm(request.POST, email=member.email)
            if not form.is_valid():
                return _rendre_invitation(request, etat, member, form)
            user = form.save()
            login(request, user)
        invitations.accepter(member, user)
        # Le rattachement vient de naître : le contexte d'espaces posé par le
        # middleware en début de requête l'ignore encore.
        espaces_service.invalider(request)
        # L'invitation porte sur l'espace employé : l'ouvrir tout de suite,
        # sans quoi un exploitant invité resterait sur son espace habituel.
        espaces_service.definir_espace(request, EMPLOYE)
        messages.success(request, _("Bienvenue dans l'équipe de %(expl)s.")
                         % {"expl": member.exploitation.name})
        return redirect("core:dashboard")

    return _rendre_invitation(request, etat, member, form)


def _rendre_invitation(request, etat, member, form):
    return render(request, "equipe/invitation.html", {
        "etat": etat, "membre": member, "form": form,
        "url_connexion": f"{reverse('accounts:login')}?next={request.path}",
        "page_title": _("Invitation"),
    })


@login_required
@require_POST
def membre_delete(request, pk):
    """Supprime un membre d'équipe."""
    exploitation = _exploitation(request)
    get_object_or_404(TeamMember, pk=pk, exploitation=exploitation).delete()
    messages.success(request, _("Membre supprimé."))
    return redirect("equipe:equipe")


@login_required
def taches(request):
    exploitation = _exploitation(request)
    form = TaskForm(exploitation=exploitation)
    if request.method == "POST":
        if exploitation is None:
            messages.error(request, _("Créez d'abord votre exploitation avant d'ajouter une tâche."))
        else:
            form = TaskForm(request.POST, exploitation=exploitation)
            if form.is_valid():
                task = form.save(commit=False)
                task.exploitation = exploitation
                task.created_by = request.user
                task.save()
                messages.success(request, _("Tâche « %(t)s » ajoutée.") % {"t": task.title})
                return redirect("equipe:taches")
    # « Mes tâches » : membre lié à mon compte (par user, ou à défaut par email).
    my_member = None
    if exploitation:
        q = Q(user=request.user)
        if request.user.email:
            q |= Q(email__iexact=request.user.email)
        my_member = TeamMember.objects.filter(exploitation=exploitation).filter(q).first()
    tasks = list(
        Task.objects.filter(exploitation=exploitation).select_related("assigned_to")
        if exploitation else Task.objects.none()
    )
    for t in tasks:
        t.is_mine = my_member is not None and t.assigned_to_id == my_member.id
    has_mine = any(t.is_mine for t in tasks)
    return render(request, "equipe/taches.html", {
        "tasks": tasks, "form": form, "has_mine": has_mine,
        "priorities": Task.Priority.choices, "statuses": Task.Status.choices,
        "page_title": _("Tâches"),
    })


@login_required
def taches_edit(request, pk):
    """Modifie une tâche (soumis depuis la modale de /taches/)."""
    exploitation = _exploitation(request)
    task = get_object_or_404(Task, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, exploitation=exploitation)
        if form.is_valid():
            form.save()
            messages.success(request, _("Tâche « %(t)s » modifiée.") % {"t": task.title})
        else:
            messages.error(request, _("Modification impossible : vérifiez les champs."))
    return redirect("equipe:taches")


@login_required
@require_POST
def taches_delete(request, pk):
    """Supprime une tâche."""
    exploitation = _exploitation(request)
    get_object_or_404(Task, pk=pk, exploitation=exploitation).delete()
    messages.success(request, _("Tâche supprimée."))
    return redirect("equipe:taches")


def location_share(request, token):
    """Page publique de partage de position (lien 24h)."""
    member = TeamMember.objects.filter(
        location_token=token, location_token_expires_at__gt=timezone.now()
    ).first()
    return render(request, "equipe/location_share.html", {"member": member, "token": token})


def _rh_placeholder(request, title):
    """Page « en préparation » pour une sous-section RH."""
    return render(request, "equipe/placeholder.html", {"title": title, "page_title": title})


@login_required
@espace_requis(EXPLOITANT)
def contrats(request):
    """Contrats de travail — module RH en préparation."""
    return _rh_placeholder(request, _("Contrats de travail"))


@login_required
@espace_requis(EXPLOITANT)
def paie(request):
    """Paie — module RH en préparation."""
    return _rh_placeholder(request, _("Paie"))
