"""Référentiel de base des espèces d'élevage, partagé par toutes les exploitations.

Le modèle Espece n'a pas de rattachement à une exploitation : ces fiches sont
communes. Les livrer en migration les rend disponibles dans tous les
environnements, au lieu de vivre dans une seule base.
"""

from django.db import migrations

ESPECES = [
    {"nom": "Boeuf", "famille": "bovins", "production": "viande"},
    {"nom": "Veau", "famille": "bovins", "production": "viande"},
    {"nom": "Mouton", "famille": "ovins", "production": "mixte"},
    {"nom": "Chèvre", "famille": "caprins", "production": "mixte"},
    {"nom": "Cochon", "famille": "porcins", "production": "mixte"},
]


def seed(apps, schema_editor):
    Espece = apps.get_model("elevage", "Espece")
    for fiche in ESPECES:
        # Idempotent : une fiche déjà saisie est mise à jour, jamais dupliquée.
        Espece.objects.update_or_create(
            nom=fiche["nom"],
            defaults={k: v for k, v in fiche.items() if k != "nom"},
        )


def unseed(apps, schema_editor):
    Espece = apps.get_model("elevage", "Espece")
    Espece.objects.filter(nom__in=[f["nom"] for f in ESPECES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("elevage", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
