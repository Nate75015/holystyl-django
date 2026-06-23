"""Vues web messagerie : boîte de réception, fil de discussion, nouvelle conversation."""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from equipe.models import TeamMember
from exploitations.models import Exploitation

from .models import Conversation, ConversationMember, Message, PieceJointe, validate_piece_jointe

User = get_user_model()


def _candidate_users(request):
    """Utilisateurs contactables : owner + membres d'équipe (liés à un compte)
    des exploitations dont l'utilisateur est propriétaire ou membre."""
    user_ids = set()
    exploitations = Exploitation.objects.filter(owner=request.user) | Exploitation.objects.filter(
        team_members__user=request.user
    )
    for exploitation in exploitations.distinct():
        user_ids.add(exploitation.owner_id)
        user_ids.update(
            TeamMember.objects.filter(exploitation=exploitation, user__isnull=False).values_list("user_id", flat=True)
        )
    user_ids.discard(request.user.id)
    return User.objects.filter(id__in=user_ids).order_by("full_name", "email")


def _mark_read(conversation, user):
    ConversationMember.objects.filter(conversation=conversation, user=user).update(last_read_at=timezone.now())


@login_required
def inbox(request):
    conversations = list(
        Conversation.objects.filter(memberships__user=request.user)
        .prefetch_related("participants", "messages")
        .distinct()
    )
    for c in conversations:
        c.title = c.display_name(request.user)
        last = c.last_message()
        if last:
            c.preview = last.body or (_("📎 Pièce jointe") if last.pieces_jointes.exists() else "")
        else:
            c.preview = ""
        c.unread = c.unread_count(request.user)
    conversations.sort(key=lambda c: c.updated_at, reverse=True)
    return render(request, "messagerie/inbox.html", {"conversations": conversations, "page_title": _("Messagerie")})


@login_required
def detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, memberships__user=request.user)
    conversation.title = conversation.display_name(request.user)
    _mark_read(conversation, request.user)
    return render(request, "messagerie/detail.html", {"conversation": conversation, "page_title": conversation.title})


@login_required
def thread(request, pk):
    """Fragment HTMX : liste des messages (polling) + marque comme lu."""
    conversation = get_object_or_404(Conversation, pk=pk, memberships__user=request.user)
    _mark_read(conversation, request.user)
    return render(request, "messagerie/_messages.html", {"conversation": conversation})


@login_required
@require_POST
def send(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, memberships__user=request.user)
    body = (request.POST.get("body") or "").strip()

    valid_files, errors = [], []
    for f in request.FILES.getlist("fichiers"):
        try:
            validate_piece_jointe(f)
            valid_files.append(f)
        except ValidationError as exc:
            errors.append(exc.message if hasattr(exc, "message") else str(exc))

    if body or valid_files:
        message = Message.objects.create(conversation=conversation, sender=request.user, body=body)
        for f in valid_files:
            PieceJointe.objects.create(message=message, fichier=f, nom=f.name)
        Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

    _mark_read(conversation, request.user)
    return render(request, "messagerie/_messages.html", {"conversation": conversation, "errors": errors})


@login_required
def new(request):
    candidates = _candidate_users(request)
    if request.method == "POST":
        ids = request.POST.getlist("participants")
        name = (request.POST.get("name") or "").strip()
        users = list(candidates.filter(id__in=ids))
        if users:
            is_group = len(users) > 1 or bool(name)
            conversation = None
            if not is_group:
                conversation = (
                    Conversation.objects.filter(is_group=False, memberships__user=request.user)
                    .filter(memberships__user=users[0])
                    .first()
                )
            if conversation is None:
                conversation = Conversation.objects.create(
                    is_group=is_group, name=name, created_by=request.user,
                    exploitation=Exploitation.objects.filter(owner=request.user).first(),
                )
                ConversationMember.objects.get_or_create(conversation=conversation, user=request.user)
                for u in users:
                    ConversationMember.objects.get_or_create(conversation=conversation, user=u)
            return redirect("messagerie:detail", pk=conversation.pk)
    return render(request, "messagerie/new.html", {"candidates": candidates, "page_title": _("Nouvelle conversation")})
