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
    nom_usage = models.CharField(
        _("nom d'usage"), max_length=160, blank=True,
        help_text=_("S'il diffère du nom de famille : c'est souvent lui qui figure "
                    "sur les contrats."))
    numero = models.CharField(_("numéro"), max_length=60, blank=True)
    autorite = models.CharField(
        _("autorité de délivrance"), max_length=160, blank=True,
        help_text=_("Préfecture, sous-préfecture, mairie ou consulat."))
    delivre_le = models.DateField(_("délivrée le"), null=True, blank=True)
    expire_le = models.DateField(
        _("expire le"), null=True, blank=True,
        help_text=_("La date imprimée sur la pièce."))
    #: Les cartes délivrées à un majeur entre 2004 et 2013 ont été prolongées
    #: de cinq ans sans que la date imprimée change. Plusieurs pays refusent
    #: cette prolongation pour un voyage : les deux dates comptent donc, et
    #: pas pour le même usage.
    prolongee = models.BooleanField(
        _("validité prolongée de 5 ans"), default=False,
        help_text=_("Carte délivrée à un majeur entre 2004 et 2013 : valable cinq ans "
                    "de plus en France, mais refusée par certains pays à l'étranger."))
    fichier = models.FileField(_("fichier"), upload_to="identite/%Y/%m/")
    #: Signature seulement : celle qui s'appose sur les documents. Une
    #: personne en a souvent plusieurs versions — on désigne celle qui vaut.
    par_defaut = models.BooleanField(_("signature active"), default=False)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("pièce d'identité")
        verbose_name_plural = _("pièces d'identité")
        ordering = ("type_piece", "-created_at")
        indexes = [models.Index(fields=["exploitation", "type_piece"])]

    def __str__(self):
        return f"{self.get_type_piece_display()} — {self.titulaire or self.numero}".strip(" —")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Une seule signature active à la fois : la nouvelle chasse l'ancienne.
        if self.par_defaut and self.est_signature:
            Piece.objects.filter(exploitation=self.exploitation,
                                 type_piece=self.Type.SIGNATURE,
                                 par_defaut=True).exclude(pk=self.pk).update(par_defaut=False)

    @classmethod
    def signature_active(cls, exploitation):
        """La signature qui s'appose sur les documents, ou None.

        À défaut de signature désignée, la plus récente : mieux vaut une
        signature que rien sur un contrat qui part au salarié.
        """
        if exploitation is None:
            return None
        base = cls.objects.filter(exploitation=exploitation, type_piece=cls.Type.SIGNATURE)
        return base.filter(par_defaut=True).first() or base.order_by("-created_at").first()

    @property
    def est_signature(self) -> bool:
        return self.type_piece == self.Type.SIGNATURE

    @property
    def expiration_reelle(self):
        """La date qui fait foi en France, prolongation comprise.

        La pièce en porte une autre : c'est celle-là qu'un contrôle à
        l'étranger regardera.
        """
        if not self.expire_le:
            return None
        if not self.prolongee:
            return self.expire_le
        try:
            return self.expire_le.replace(year=self.expire_le.year + 5)
        except ValueError:
            # 29 février : l'année d'arrivée n'est pas forcément bissextile.
            from datetime import date

            return date(self.expire_le.year + 5, 3, 1)

    @property
    def prolongation_douteuse(self) -> bool:
        """Vrai quand la date imprimée et la date réelle divergent."""
        return bool(self.prolongee and self.expire_le)

    @property
    def jours_avant_expiration(self):
        """Jours restants ; négatif si la pièce est périmée.

        On compte sur la date qui fait foi, pas sur celle qui est imprimée :
        alerter sur une carte encore valable cinq ans serait du bruit.
        """
        from django.utils import timezone

        echeance = self.expiration_reelle
        if not echeance:
            return None
        return (echeance - timezone.localdate()).days

    @property
    def perimee(self) -> bool:
        restant = self.jours_avant_expiration
        return restant is not None and restant < 0

    @property
    def expire_bientot(self) -> bool:
        restant = self.jours_avant_expiration
        return restant is not None and 0 <= restant <= self.JOURS_ALERTE
