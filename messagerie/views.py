"""Vues web messagerie : boîte de réception, fil de discussion, nouvelle conversation."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from equipe.models import TeamMember
from exploitations.models import Exploitation
from ia import llm

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


def _farmers(request):
    """Personnes contactables : uniquement le réseau (connexions acceptées)."""
    from reseaux.models import Connexion

    ids = Connexion.connected_user_ids(request.user)
    return User.objects.filter(id__in=ids).order_by("full_name", "email")


def _mark_read(conversation, user):
    ConversationMember.objects.filter(conversation=conversation, user=user).update(last_read_at=timezone.now())


def _time_label(dt):
    """Horodatage façon WhatsApp : heure (aujourd'hui), jour (semaine), date (au-delà)."""
    if dt is None:
        return ""
    now = timezone.localtime()
    local = timezone.localtime(dt)
    delta = now.date() - local.date()
    if delta.days == 0:
        return local.strftime("%H:%M")
    if delta.days == 1:
        return _("Hier")
    if delta.days < 7:
        jours = [_("lun."), _("mar."), _("mer."), _("jeu."), _("ven."), _("sam."), _("dim.")]
        return jours[local.weekday()]
    return local.strftime("%d/%m/%Y")


def _conversations(request):
    """Liste des conversations de l'utilisateur, enrichie (titre, aperçu, non lus)."""
    conversations = list(
        Conversation.objects.filter(memberships__user=request.user)
        .prefetch_related("participants", "messages")
        .distinct()
    )
    for c in conversations:
        c.title = c.display_name(request.user)
        last = c.last_message()
        c.preview = (last.body or (_("📎 Pièce jointe") if last.pieces_jointes.exists() else "")) if last else ""
        c.unread = c.unread_count(request.user)
        c.last_at = last.created_at if last else c.updated_at
        c.time_label = _time_label(c.last_at)
    conversations.sort(key=lambda c: c.last_at, reverse=True)
    return conversations


@login_required
def inbox(request):
    return render(
        request,
        "messagerie/inbox.html",
        {
            "conversations": _conversations(request),
            "farmers": _farmers(request),
            "current_pk": None,
            "page_title": _("Messagerie"),
        },
    )


@login_required
def start(request, user_id):
    """Ouvre (ou crée) une conversation 1:1 avec une personne de son réseau."""
    from reseaux.models import Connexion

    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other.pk == request.user.pk:
        return redirect("messagerie:inbox")
    # On ne peut échanger qu'avec les personnes connectées (réseau accepté).
    if not Connexion.are_connected(request.user, other):
        messages.warning(request, _("Connectez-vous à cette personne (Réseau) avant de lui écrire."))
        return redirect("reseaux:reseaux")
    conversation = (
        Conversation.objects.filter(is_group=False, memberships__user=request.user)
        .filter(memberships__user=other)
        .first()
    )
    if conversation is None:
        conversation = Conversation.objects.create(
            is_group=False,
            created_by=request.user,
            exploitation=Exploitation.objects.filter(owner=request.user).first(),
        )
        ConversationMember.objects.get_or_create(conversation=conversation, user=request.user)
        ConversationMember.objects.get_or_create(conversation=conversation, user=other)
    return redirect("messagerie:detail", pk=conversation.pk)


@login_required
@require_POST
def reformulate(request):
    """Reformule un message via l'IA (repli : renvoie le texte original)."""
    text = (request.POST.get("text") or "").strip()
    if not text or not llm.is_configured():
        return JsonResponse({"text": text})
    try:
        out = llm.generate_text(
            [
                {"role": "system", "content": (
                    "Tu reformules des messages de messagerie professionnelle agricole pour les rendre "
                    "clairs, polis et bien écrits, en français. Conserve le sens et la langue. Réponds "
                    "UNIQUEMENT par le message reformulé, sans guillemets ni préambule."
                )},
                {"role": "user", "content": text[:2000]},
            ],
            temperature=0.5,
        )
        return JsonResponse({"text": (out or text).strip()})
    except Exception:  # noqa: BLE001 — indispo IA → repli sur l'original
        return JsonResponse({"text": text})


@login_required
def detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, memberships__user=request.user)
    conversation.title = conversation.display_name(request.user)
    _mark_read(conversation, request.user)
    return render(request, "messagerie/detail.html", {
        "conversation": conversation,
        "conversations": _conversations(request),
        "farmers": _farmers(request),
        "current_pk": conversation.pk,
        "page_title": conversation.title,
    })


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
    candidates = _farmers(request)
    if request.method == "POST":
        mode = request.POST.get("mode", "direct")
        message_body = (request.POST.get("message") or "").strip()
        if mode == "groupe":
            ids = request.POST.getlist("participants")
            name = (request.POST.get("name") or "").strip()
        else:
            ids = [request.POST.get("participant")] if request.POST.get("participant") else []
            name = ""

        users = list(candidates.filter(id__in=ids))
        if users:
            is_group = mode == "groupe"
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
            if message_body:
                Message.objects.create(conversation=conversation, sender=request.user, body=message_body)
                Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
            return redirect("messagerie:detail", pk=conversation.pk)
    return render(request, "messagerie/new.html", {"candidates": candidates, "page_title": _("Nouvelle conversation")})


@login_required
@require_POST
def conversation_delete(request, pk):
    """Supprime la conversation pour l'utilisateur (retire son adhésion).
    Si plus personne n'y participe, la conversation et ses messages sont supprimés."""
    conversation = get_object_or_404(Conversation, pk=pk, memberships__user=request.user)
    ConversationMember.objects.filter(conversation=conversation, user=request.user).delete()
    if not conversation.memberships.exists():
        conversation.delete()
    messages.success(request, _("Conversation supprimée."))
    return redirect("messagerie:inbox")


@login_required
@require_POST
def message_delete(request, pk):
    """Supprime un message (seul son auteur peut le faire)."""
    message = get_object_or_404(Message, pk=pk, sender=request.user)
    conversation = message.conversation
    message.delete()
    return render(request, "messagerie/_messages.html", {"conversation": conversation})
