"""Référentiel de base des espèces aquacoles, partagé par toutes les exploitations.

Même principe que les espèces d'élevage : le modèle n'est rattaché à aucune
exploitation, la migration rend ces fiches disponibles partout.
"""

from django.db import migrations

ESPECES = [
    {"nom": "Thon", "famille": "poisson_marin", "milieu": "marine", "production": "chair"},
]


def seed(apps, schema_editor):
    EspeceAquacole = apps.get_model("aquaculture", "EspeceAquacole")
    for fiche in ESPECES:
        # Idempotent : une fiche déjà saisie est mise à jour, jamais dupliquée.
        EspeceAquacole.objects.update_or_create(
            nom=fiche["nom"],
            defaults={k: v for k, v in fiche.items() if k != "nom"},
        )


def unseed(apps, schema_editor):
    EspeceAquacole = apps.get_model("aquaculture", "EspeceAquacole")
    EspeceAquacole.objects.filter(nom__in=[f["nom"] for f in ESPECES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("aquaculture", "0002_especeaquacole_souche"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
