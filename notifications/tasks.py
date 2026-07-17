"""Évaluation horaire des règles d'alerte.

Seul le type « météo » est évalué : c'est le seul dont la source de données est
branchée (`meteo.services.fetch_weather`). Les autres types du modèle restent
inertes tant qu'ils n'ont pas de source, et le formulaire ne les propose pas.

Politique de notification : alerte au *franchissement* uniquement. Une règle qui
reste dépassée pendant des heures ne notifie qu'une fois ; elle se réarme quand la
valeur repasse du bon côté du seuil (`NotificationRule.is_breaching`).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from celery import shared_task
from django.utils.translation import gettext as _

from meteo.services import fetch_weather

from .models import Notification, NotificationRule
from .services import notify

logger = logging.getLogger(__name__)


def _fmt(value: Decimal) -> str:
    """« 30.00 » → « 30 », « 12.50 » → « 12.5 ».

    `normalize()` seul renverrait « 3E+1 » : le format « f » force la virgule fixe.
    """
    return format(value.normalize(), "f")


def _breaches(value: float, condition: str, threshold: Decimal) -> bool:
    if condition == NotificationRule.ConditionType.SEUIL_DEPASSE:
        return value > float(threshold)
    if condition == NotificationRule.ConditionType.SEUIL_SOUS:
        return value < float(threshold)
    return False  # `changement_etat` n'a pas de sens sur une grandeur numérique


def _evaluate(rule: NotificationRule, current: dict) -> bool:
    """Évalue une règle contre la météo courante. Renvoie True si une alerte est émise."""
    source_key, unit = NotificationRule.METRIC_SOURCE[rule.metric]
    value = current.get(source_key)
    if value is None:
        logger.warning("Règle #%s : grandeur %s absente de la météo.", rule.pk, rule.metric)
        return False

    breaching = _breaches(float(value), rule.condition_type, rule.threshold)
    if breaching == rule.is_breaching:
        return False  # rien de neuf : ni franchissement, ni réarmement

    rule.is_breaching = breaching
    rule.save(update_fields=["is_breaching", "updated_at"])
    if not breaching:
        return False  # réarmement silencieux : la valeur est repassée sous le seuil

    sens = (
        _("dépasse")
        if rule.condition_type == NotificationRule.ConditionType.SEUIL_DEPASSE
        else _("est descendu sous")
    )
    notify(
        rule.user,
        type="alerte_meteo",
        title=rule.name,
        message=_("%(metric)s à %(lieu)s %(sens)s le seuil : %(value)s%(unit)s (seuil %(seuil)s%(unit)s).") % {
            "metric": rule.get_metric_display(),
            "lieu": rule.ville.nom,
            "sens": sens,
            "value": value,
            "unit": unit,
            "seuil": _fmt(rule.threshold),
        },
        priority=Notification.Priority.HAUTE,
        action_url=f"/meteo/{rule.ville.slug}/",
        metadata={"rule_id": rule.pk, "metric": rule.metric, "value": value},
    )
    return True


@shared_task
def evaluate_rules():
    """Passe toutes les règles météo activées en revue (une fois par heure)."""
    rules = (
        NotificationRule.objects.filter(
            enabled=True,
            type=NotificationRule.Type.METEO,
            ville__isnull=False,
            threshold__isnull=False,
        )
        .exclude(metric="")
        .select_related("ville", "user")
    )

    # Un seul appel météo par lieu, quel que soit le nombre de règles qui le visent.
    par_ville: dict[int, list[NotificationRule]] = {}
    for rule in rules:
        par_ville.setdefault(rule.ville_id, []).append(rule)

    alertes = 0
    for regles in par_ville.values():
        ville = regles[0].ville
        try:
            current = fetch_weather(ville.latitude, ville.longitude)["current"]
        except Exception:  # noqa: BLE001 — un lieu injoignable ne doit pas tuer le lot
            logger.exception("Météo indisponible pour %s : règles non évaluées.", ville.nom)
            continue
        for rule in regles:
            try:
                alertes += _evaluate(rule, current)
            except Exception:  # noqa: BLE001 — une règle en erreur ne bloque pas les suivantes
                logger.exception("Évaluation impossible pour la règle #%s.", rule.pk)

    logger.info("Règles évaluées : %s lieu(x), %s alerte(s).", len(par_ville), alertes)
    return {"lieux": len(par_ville), "alertes": alertes}
