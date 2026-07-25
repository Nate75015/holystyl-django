"""Déplace culture + irrigation de la parcelle vers une campagne « 2025/2026 ».

Chaque parcelle reçoit une campagne courante reprenant ses valeurs actuelles ;
les stades culturaux existants y sont rattachés.
"""

from django.db import migrations

CAMPAGNE_LABEL = "2025/2026"

FIELDS = [
    "culture", "variety", "kc_value", "tree_age_years", "planting_date",
    "plant_density_per_ha", "irrigation_type", "theoretical_flow_m3h",
    "nozzle_count", "nozzle_flow_lh", "row_spacing_m", "emitter_spacing_m",
    "service_pressure_bar",
]


def forward(apps, schema_editor):
    Parcelle = apps.get_model("parcelles", "Parcelle")
    ParcelleCampagne = apps.get_model("parcelles", "ParcelleCampagne")
    CropStage = apps.get_model("parcelles", "CropStage")

    for parcelle in Parcelle.objects.all():
        values = {f: getattr(parcelle, f) for f in FIELDS}
        campagne = ParcelleCampagne.objects.create(
            parcelle=parcelle, libelle=CAMPAGNE_LABEL, **values
        )
        CropStage.objects.filter(parcelle=parcelle).update(parcelle_campagne=campagne)


def backward(apps, schema_editor):
    Parcelle = apps.get_model("parcelles", "Parcelle")
    ParcelleCampagne = apps.get_model("parcelles", "ParcelleCampagne")

    for campagne in ParcelleCampagne.objects.filter(libelle=CAMPAGNE_LABEL):
        parcelle = campagne.parcelle
        for f in FIELDS:
            setattr(parcelle, f, getattr(campagne, f))
        parcelle.save(update_fields=FIELDS)
    ParcelleCampagne.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("parcelles", "0005_parcellecampagne_cropstage_parcelle_campagne_and_more"),
    ]

    operations = [migrations.RunPython(forward, backward)]
