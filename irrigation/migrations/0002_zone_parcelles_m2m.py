from django.db import migrations, models


def copier_parcelle_vers_m2m(apps, schema_editor):
    """Recopie l'unique parcelle (ancien FK) dans le nouveau M2M `parcelles`."""
    IrrigationZone = apps.get_model("irrigation", "IrrigationZone")
    for zone in IrrigationZone.objects.exclude(parcelle__isnull=True):
        zone.parcelles.add(zone.parcelle_id)


def reculer_m2m_vers_parcelle(apps, schema_editor):
    """Sens inverse : reprend la 1re parcelle du M2M comme FK unique."""
    IrrigationZone = apps.get_model("irrigation", "IrrigationZone")
    for zone in IrrigationZone.objects.all():
        first = zone.parcelles.first()
        if first is not None:
            zone.parcelle = first
            zone.save(update_fields=["parcelle"])


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0001_initial'),
        ('parcelles', '0002_parcelle_acquired_at_parcelle_cadastre_data'),
    ]

    operations = [
        # 1) Ajout du M2M (le FK `parcelle` existe encore à ce stade).
        migrations.AddField(
            model_name='irrigationzone',
            name='parcelles',
            field=models.ManyToManyField(blank=True, related_name='irrigation_zones', to='parcelles.parcelle'),
        ),
        # 2) Préservation des liens existants avant de retirer l'ancien champ.
        migrations.RunPython(copier_parcelle_vers_m2m, reculer_m2m_vers_parcelle),
        # 3) Suppression de l'ancien FK.
        migrations.RemoveField(
            model_name='irrigationzone',
            name='parcelle',
        ),
    ]
