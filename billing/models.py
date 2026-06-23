"""Facturation SaaS : codes d'activation (post-Stripe) et abonnements.

Fidèle aux tables Drizzle `activation_codes`, `subscriptions`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ActivationCode(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        USED = "used", _("Utilisé")
        EXPIRED = "expired", _("Expiré")
        CANCELLED = "cancelled", _("Annulé")

    code = models.CharField(max_length=64, unique=True)
    email = models.EmailField()
    stripe_session_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.SET_NULL, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("code d'activation")
        verbose_name_plural = _("codes d'activation")
        ordering = ("-created_at",)

    def __str__(self):
        return self.code


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Actif")
        PAST_DUE = "past_due", _("Impayé")
        CANCELLED = "cancelled", _("Annulé")
        TRIALING = "trialing", _("Essai")
        UNPAID = "unpaid", _("Non payé")

    exploitation = models.OneToOneField("exploitations.Exploitation", on_delete=models.CASCADE, related_name="subscription")
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("abonnement")
        verbose_name_plural = _("abonnements")
