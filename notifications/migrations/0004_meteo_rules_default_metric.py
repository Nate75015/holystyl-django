"""Renseigne la grandeur des règles météo créées avant l'existence du champ `metric`.

Ces règles ont été saisies quand le formulaire ne demandait pas de grandeur : elles
portent un seuil sans dire de quoi. La température est la seule interprétation
raisonnable (c'est ce que les seuils météo désignent en pratique), et sans elle la
tâche d'évaluation les ignorerait silencieusement.
"""

from django.db import migrations


def set_default_metric(apps, schema_editor):
    NotificationRule = apps.get_model("notifications", "NotificationRule")
    NotificationRule.objects.filter(type="meteo", metric="").update(metric="temperature")


def unset_metric(apps, schema_editor):
    NotificationRule = apps.get_model("notifications", "NotificationRule")
    NotificationRule.objects.filter(type="meteo", metric="temperature").update(metric="")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_notificationrule_is_breaching_and_more"),
    ]

    operations = [
        migrations.RunPython(set_default_metric, unset_metric),
    ]
