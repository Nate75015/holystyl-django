"""Sondages : question unique + choix, un vote par utilisateur, résultats."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Sondage(TimeStampedModel):
    exploitation = models.ForeignKey(
        "exploitations.Exploitation", on_delete=models.CASCADE,
        null=True, blank=True, related_name="sondages",
    )
    question = models.CharField(_("question"), max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    closed = models.BooleanField(_("clôturé"), default=False)

    class Meta:
        verbose_name = _("sondage")
        verbose_name_plural = _("sondages")
        ordering = ("-created_at",)

    def __str__(self):
        return self.question

    def total_votes(self):
        return Vote.objects.filter(sondage=self).count()

    def user_vote(self, user):
        """Choix voté par `user`, ou None."""
        v = Vote.objects.filter(sondage=self, user=user).select_related("choix").first()
        return v.choix if v else None

    def results(self):
        """Liste de dicts {choix, count, pct} triés par ordre des choix."""
        total = self.total_votes()
        data = []
        for choix in self.choix.all():
            count = choix.votes.count()
            pct = round(count * 100 / total) if total else 0
            data.append({"choix": choix, "count": count, "pct": pct})
        return data


class Choix(models.Model):
    sondage = models.ForeignKey(Sondage, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(_("texte"), max_length=255)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("choix")
        verbose_name_plural = _("choix")
        ordering = ("ordre", "id")

    def __str__(self):
        return self.texte


class Vote(models.Model):
    sondage = models.ForeignKey(Sondage, on_delete=models.CASCADE, related_name="votes")
    choix = models.ForeignKey(Choix, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("vote")
        verbose_name_plural = _("votes")
        unique_together = ("sondage", "user")

    def __str__(self):
        return f"{self.user} → {self.choix}"
