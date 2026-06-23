"""Modèle utilisateur Holystyl — authentification par email/mot de passe."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """Utilisateur identifié par son email (le champ username est supprimé)."""

    username = None
    email = models.EmailField(_("adresse email"), unique=True)
    full_name = models.CharField(_("nom complet"), max_length=255, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")

    def __str__(self):
        return self.email

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]
