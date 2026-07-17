"""Taxonomie EU — fiches d'activité et évaluation d'alignement (règlement UE 2020/852)."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ActiviteTaxonomie(models.Model):
    """Une fiche = une activité économique évaluée au regard de la Taxonomie EU."""

    class Objectif(models.TextChoices):
        ATTENUATION = "attenuation", _("Atténuation du changement climatique")
        ADAPTATION = "adaptation", _("Adaptation au changement climatique")
        EAU = "eau", _("Eau et ressources marines")
        CIRCULAIRE = "circulaire", _("Économie circulaire")
        POLLUTION = "pollution", _("Prévention de la pollution")
        BIODIVERSITE = "biodiversite", _("Biodiversité et écosystèmes")

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="activites_taxonomie"
    )
    campagne = models.PositiveIntegerField(_("campagne"))
    libelle = models.CharField(_("activité"), max_length=255)
    code_nace = models.CharField(_("code NACE"), max_length=20, blank=True)
    objectif = models.CharField(
        _("objectif de contribution"), max_length=15, choices=Objectif.choices, default=Objectif.ATTENUATION
    )
    eligible = models.BooleanField(_("éligible"), default=False)
    contribution = models.BooleanField(_("contribution substantielle"), default=False)
    # DNSH : {"adaptation": true, "eau": false, …} — un statut par objectif
    dnsh = models.JSONField(_("DNSH par objectif"), default=dict, blank=True)
    garanties = models.BooleanField(_("garanties minimales"), default=False)
    chiffre_affaires = models.FloatField(_("chiffre d'affaires (€)"), null=True, blank=True)
    capex = models.FloatField(_("CapEx (€)"), null=True, blank=True)
    opex = models.FloatField(_("OpEx (€)"), null=True, blank=True)
    justification = models.TextField(_("justification"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("activité Taxonomie")
        verbose_name_plural = _("activités Taxonomie")
        ordering = ("-campagne", "libelle")
        indexes = [models.Index(fields=["exploitation", "campagne"])]

    def __str__(self):
        return f"{self.libelle} ({self.campagne})"

    @property
    def autres_objectifs(self):
        """Les 5 objectifs autres que celui de contribution (cibles du DNSH)."""
        return [o for o in self.Objectif.values if o != self.objectif]

    @property
    def dnsh_ok(self):
        return all(self.dnsh.get(o, False) for o in self.autres_objectifs)

    @property
    def aligne(self):
        """Activité alignée = éligible + contribution + DNSH (5 autres) + garanties."""
        return bool(self.eligible and self.contribution and self.garanties and self.dnsh_ok)

    @property
    def statut(self):
        if self.aligne:
            return "aligne"
        if self.eligible:
            return "eligible"
        return "non_eligible"


class Biodiversite(models.Model):
    """Fiche de suivi de la biodiversité d'une parcelle (IAE, espèces, couverts)."""

    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE, related_name="fiches_biodiversite"
    )
    parcelle = models.ForeignKey(
        "parcelles.Parcelle", on_delete=models.CASCADE, related_name="fiches_biodiversite"
    )
    date = models.DateField(_("date"))
    score = models.IntegerField(_("score biodiversité (0-100)"), null=True, blank=True)
    especes_vegetales = models.IntegerField(_("espèces végétales"), null=True, blank=True)
    especes_animales = models.IntegerField(_("espèces animales"), null=True, blank=True)
    haies_ml = models.FloatField(_("haies (ml)"), null=True, blank=True)
    jachere_ha = models.FloatField(_("jachère (ha)"), null=True, blank=True)
    observations = models.TextField(_("observations"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("fiche biodiversité")
        verbose_name_plural = _("fiches biodiversité")
        ordering = ("-date",)

    def __str__(self):
        return f"{self.parcelle} — {self.date}"
