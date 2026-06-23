"""Messagerie : conversations 1-à-1 et groupe entre utilisateurs d'une exploitation."""

import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "odt", "ods",
    "txt", "csv", "png", "jpg", "jpeg", "gif", "webp",
}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 Mo


def validate_piece_jointe(fichier):
    """Valide l'extension et la taille d'un fichier joint (5 Mo max)."""
    _root, ext = os.path.splitext(fichier.name)
    if ext.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("Extension non autorisée : %(ext)s. Extensions acceptées : %(list)s.")
            % {"ext": ext, "list": ", ".join(sorted(ALLOWED_EXTENSIONS))}
        )
    if fichier.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            _("Le fichier dépasse la taille maximale de 5 Mo (%(got)s Mo reçus).")
            % {"got": fichier.size // 1024 // 1024}
        )


class Conversation(TimeStampedModel):
    """Un fil de discussion, privé (2 personnes) ou de groupe (3+)."""

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        null=True, blank=True, related_name="conversations",
    )
    is_group = models.BooleanField(_("groupe"), default=False)
    name = models.CharField(_("nom du groupe"), max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="ConversationMember", related_name="conversations"
    )

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ("-updated_at",)

    def __str__(self):
        return self.name or f"Conversation #{self.pk}"

    # ── Helpers d'affichage (appelés depuis les vues, jamais avec request.user en template) ──
    def display_name(self, user):
        if self.is_group:
            if self.name:
                return self.name
            others = [p.display_name for p in self.participants.all() if p != user]
            return ", ".join(others) or _("Groupe")
        other = next((p for p in self.participants.all() if p != user), None)
        return other.display_name if other else _("Conversation")

    def last_message(self):
        return self.messages.order_by("-created_at").first()

    def unread_count(self, user):
        membership = self.memberships.filter(user=user).first()
        qs = self.messages.exclude(sender=user)
        if membership and membership.last_read_at:
            qs = qs.filter(created_at__gt=membership.last_read_at)
        return qs.count()


class ConversationMember(models.Model):
    """Appartenance d'un utilisateur à une conversation + suivi de lecture."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships")
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("membre de conversation")
        verbose_name_plural = _("membres de conversation")
        unique_together = ("conversation", "user")

    def __str__(self):
        return f"{self.user} @ {self.conversation_id}"


class Message(TimeStampedModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    body = models.TextField(_("message"))

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ("created_at",)

    def __str__(self):
        return self.body[:50]


class PieceJointe(models.Model):
    """Fichier joint à un message."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="pieces_jointes")
    fichier = models.FileField(_("fichier"), upload_to="messagerie/", validators=[validate_piece_jointe])
    nom = models.CharField(_("nom"), max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("pièce jointe")
        verbose_name_plural = _("pièces jointes")
        ordering = ("created_at",)

    def __str__(self):
        return self.nom
