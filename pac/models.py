from django.db import models
from django.utils.translation import gettext_lazy as _


class AidePAC(models.Model):
    """Une aide PAC (Politique Agricole Commune) déclarée pour une campagne."""

    class Categorie(models.TextChoices):
        DPB = "DPB", _("DPB — Droits à paiement de base")
        ECO_REGIME = "ECO", _("Éco-régime")
        REDISTRIBUTIF = "REDIST", _("Paiement redistributif")
        JEUNE = "JA", _("Aide jeune agriculteur")
        COUPLEE = "COUPLEE", _("Aides couplées")
        ICHN = "ICHN", _("ICHN — Indemnité handicap naturel")
        MAEC = "MAEC", _("MAEC — Mesures agro-environnementales")
        BIO = "BIO", _("Agriculture biologique")
        ASSURANCE = "ASSUR", _("Assurance récolte")
        AUTRE = "AUTRE", _("Autre")

    class Statut(models.TextChoices):
        PREVU = "prevu", _("Prévu")
        ACCORDE = "accorde", _("Accordé")
        PAYE = "paye", _("Payé")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="aides_pac"
    )
    # Libellé de campagne agricole, partagé avec les parcelles (« 2025/2026 »).
    campagne = models.CharField(
        _("campagne"), max_length=20,
        help_text=_("Campagne agricole, ex. « 2025/2026 » (voir Mes parcelles › Campagnes)."),
    )
    categorie = models.CharField(_("catégorie"), max_length=10, choices=Categorie.choices, default=Categorie.DPB)
    libelle = models.CharField(_("libellé"), max_length=255, blank=True)
    montant = models.FloatField(_("montant (€)"), null=True, blank=True)
    surface_ha = models.FloatField(_("surface (ha)"), null=True, blank=True)
    statut = models.CharField(_("statut"), max_length=10, choices=Statut.choices, default=Statut.PREVU)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("aide PAC")
        verbose_name_plural = _("aides PAC")
        ordering = ("-campagne", "categorie")
        indexes = [models.Index(fields=["exploitation", "campagne"])]

    def __str__(self):
        return f"{self.get_categorie_display()} {self.campagne}"
