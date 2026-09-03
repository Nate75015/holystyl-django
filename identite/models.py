"""Les pièces d'identité de l'exploitant, et sa signature.

Une carte et un passeport se périment, et on s'en aperçoit toujours trop
tard — au moment d'un contrôle, d'un dossier de subvention, d'un voyage. La
date d'expiration est donc un champ, pas une note, et la page la surveille.

La signature n'a pas d'échéance mais la même nature : une pièce personnelle
qu'on redemande sans cesse et qu'on ne retrouve jamais.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Piece(models.Model):
    """Une pièce d'identité ou une signature, rangée une fois pour toutes."""

    class Type(models.TextChoices):
        CARTE = "carte", _("Carte d'identité")
        PASSEPORT = "passeport", _("Passeport")
        SIGNATURE = "signature", _("Signature")

    #: Ce qui s'ouvre partout, sans imposer un lecteur particulier.
    EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic"}
    TAILLE_MAX = 10 * 1024 * 1024
    #: En deçà, la page alerte : une pièce se renouvelle avec des délais.
    JOURS_ALERTE = 90

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="pieces_identite")
    type_piece = models.CharField(_("type"), max_length=12, choices=Type.choices)
    titulaire = models.CharField(
        _("titulaire"), max_length=160, blank=True,
        help_text=_("À qui appartient la pièce, si ce n'est pas vous."))
    numero = models.CharField(_("numéro"), max_length=60, blank=True)
    delivre_le = models.DateField(_("délivrée le"), null=True, blank=True)
    expire_le = models.DateField(_("expire le"), null=True, blank=True)
    fichier = models.FileField(_("fichier"), upload_to="identite/%Y/%m/")
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("pièce d'identité")
        verbose_name_plural = _("pièces d'identité")
        ordering = ("type_piece", "-created_at")
        indexes = [models.Index(fields=["exploitation", "type_piece"])]

    def __str__(self):
        return f"{self.get_type_piece_display()} — {self.titulaire or self.numero}".strip(" —")

    @property
    def est_signature(self) -> bool:
        return self.type_piece == self.Type.SIGNATURE

    @property
    def jours_avant_expiration(self):
        """Jours restants ; négatif si la pièce est périmée."""
        from django.utils import timezone

        if not self.expire_le:
            return None
        return (self.expire_le - timezone.localdate()).days

    @property
    def perimee(self) -> bool:
        restant = self.jours_avant_expiration
        return restant is not None and restant < 0

    @property
    def expire_bientot(self) -> bool:
        restant = self.jours_avant_expiration
        return restant is not None and 0 <= restant <= self.JOURS_ALERTE
