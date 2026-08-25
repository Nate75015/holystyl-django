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

    # first_name / last_name sont hérités d'AbstractUser (prénom / nom).
    birth_date = models.DateField(_("date de naissance"), null=True, blank=True)

    # Adresse postale
    address_number = models.CharField(_("n° de rue"), max_length=20, blank=True)
    address_street = models.CharField(_("rue"), max_length=255, blank=True)
    address_zip = models.CharField(_("code postal"), max_length=16, blank=True)
    address_city = models.CharField(_("ville"), max_length=128, blank=True)

    #: Profil déclaré à la première connexion, faute d'invitation. Il ne donne
    #: aucun droit : seul un rattachement ouvre un espace (`core.espaces`). Il
    #: sert à orienter l'accueil — créer son exploitation, ou attendre d'être
    #: rattaché par celle qui vous emploie.
    profil_souhaite = models.CharField(_("profil déclaré"), max_length=20, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # full_name reste la source d'affichage (display_name) : on le dérive
        # du prénom + nom dès qu'ils sont renseignés.
        derived = f"{self.first_name} {self.last_name}".strip()
        if derived:
            self.full_name = derived
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]
