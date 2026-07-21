"""Supprime les doublons de cultures (même nom) présents dans la base initiale.
On conserve l'entrée dotée d'un calendrier de semis/récolte si elle existe."""

from collections import defaultdict

from django.db import migrations


def dedupe(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    groups = defaultdict(list)
    for c in CultureKc.objects.all().order_by("id"):
        groups[c.nom.strip()].append(c)
    for _nom, rows in groups.items():
        if len(rows) < 2:
            continue
        keep = next((r for r in rows if r.semis_debut), rows[0])
        for r in rows:
            if r.id != keep.id:
                r.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("agronomie", "0008_seed_potager_calendrier"),
    ]

    operations = [migrations.RunPython(dedupe, noop)]
