"""Applique le nouveau défaut (12 h, ancré sur 06:00/18:00) aux villes jamais configurées.

Changer le `default` d'un champ ne touche que les lignes futures. Sans cette
migration, les villes déjà enregistrées resteraient en « quotidienne, désactivée »
alors qu'elles n'ont jamais été réglées — l'ancien défaut, pas un choix.

D'où le filtre : on ne reprend que les lignes qui portent **exactement** l'ancien
défaut et n'ont jamais capturé. Une ville dont quelqu'un a coché la case, changé
la fréquence ou déjà déclenché une capture garde son réglage.
"""

from django.db import migrations

ANCIEN_DEFAUT = {"capture_auto": False, "capture_frequence": 24, "capture_last_run": None}
NOUVEAU_DEFAUT = {"capture_auto": True, "capture_frequence": 12, "capture_heure_debut": 6}


def appliquer(apps, schema_editor):
    apps.get_model("meteo", "VilleMeteo").objects.filter(**ANCIEN_DEFAUT).update(**NOUVEAU_DEFAUT)


def revenir(apps, schema_editor):
    # Symétrique : ne rendre à l'ancien défaut que ce qui porte le nouveau, intact.
    apps.get_model("meteo", "VilleMeteo").objects.filter(
        capture_last_run=None, **NOUVEAU_DEFAUT
    ).update(capture_auto=False, capture_frequence=24)


class Migration(migrations.Migration):

    dependencies = [("meteo", "0006_villemeteo_capture_heure_debut_and_more")]

    operations = [migrations.RunPython(appliquer, revenir)]
