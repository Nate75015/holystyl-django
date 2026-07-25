"""Retire culture + irrigation de Parcelle et rend CropStage.parcelle_campagne requis.

Les données ont été déplacées vers ParcelleCampagne par la migration 0006 ;
chaque CropStage y est déjà rattaché, l'alter NOT NULL est donc sûr.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parcelles", "0006_migrate_culture_irrigation_to_campagne"),
    ]

    operations = [
        migrations.RemoveField(model_name="cropstage", name="parcelle"),
        migrations.AlterField(
            model_name="cropstage",
            name="parcelle_campagne",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="crop_stages",
                to="parcelles.parcellecampagne",
            ),
        ),
        migrations.RemoveField(model_name="parcelle", name="culture"),
        migrations.RemoveField(model_name="parcelle", name="variety"),
        migrations.RemoveField(model_name="parcelle", name="kc_value"),
        migrations.RemoveField(model_name="parcelle", name="tree_age_years"),
        migrations.RemoveField(model_name="parcelle", name="planting_date"),
        migrations.RemoveField(model_name="parcelle", name="plant_density_per_ha"),
        migrations.RemoveField(model_name="parcelle", name="irrigation_type"),
        migrations.RemoveField(model_name="parcelle", name="theoretical_flow_m3h"),
        migrations.RemoveField(model_name="parcelle", name="nozzle_count"),
        migrations.RemoveField(model_name="parcelle", name="nozzle_flow_lh"),
        migrations.RemoveField(model_name="parcelle", name="row_spacing_m"),
        migrations.RemoveField(model_name="parcelle", name="emitter_spacing_m"),
        migrations.RemoveField(model_name="parcelle", name="service_pressure_bar"),
    ]
