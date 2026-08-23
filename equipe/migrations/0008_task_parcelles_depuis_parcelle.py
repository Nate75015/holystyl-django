"""Reprend la parcelle unique de chaque tâche dans la nouvelle sélection multiple."""

from django.db import migrations


def remplir(apps, schema_editor):
    Task = apps.get_model("equipe", "Task")
    for task in Task.objects.filter(parcelle__isnull=False).only("id", "parcelle_id"):
        task.parcelles.add(task.parcelle_id)


def vider(apps, schema_editor):
    Task = apps.get_model("equipe", "Task")
    Task.parcelles.through.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [("equipe", "0007_task_parcelles")]

    operations = [migrations.RunPython(remplir, vider)]
