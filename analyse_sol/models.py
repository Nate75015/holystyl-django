"""Analyses de sol — analyses chimiques de sol par parcelle."""

from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _


def document_upload_path(instance, filename):
    """Range le document dans : analyses_sol/<parcelle>/<année>/<mois>/<fichier>."""
    parcelle = getattr(instance.parcelle, "name", "") or "parcelle"
    parcelle = get_valid_filename(parcelle) or "parcelle"
    d = instance.date or timezone.now()
    return f"analyses_sol/{parcelle}/{d:%Y}/{d:%m}/{get_valid_filename(filename)}"


class AnalyseSol(models.Model):
    """Analyse chimique de sol saisie manuellement."""

    exploitation = models.ForeignKey("exploitations.Exploitation", on_delete=models.CASCADE, related_name="analyses_sol")
    parcelle = models.ForeignKey("parcelles.Parcelle", on_delete=models.CASCADE, related_name="analyses_sol")
    date = models.DateTimeField()
    ph = models.FloatField(null=True, blank=True)
    ec = models.FloatField(null=True, blank=True)
    azote_total = models.FloatField(null=True, blank=True)
    phosphore_assimilable = models.FloatField(null=True, blank=True)
    potassium_echangeable = models.FloatField(null=True, blank=True)
    matiere_organique = models.FloatField(null=True, blank=True)
    calcaire_total = models.FloatField(null=True, blank=True)
    laboratoire = models.CharField(max_length=255, blank=True)
    document = models.FileField(_("document"), upload_to=document_upload_path, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("analyse de sol")
        verbose_name_plural = _("analyses de sol")
        ordering = ("-date",)
