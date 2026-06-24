"""Seed du référentiel TypeSol — caractéristiques hydriques par texture."""

from django.db import migrations

TEX = {
    "argileux": "argileux",
    "argilo-limoneux": "argilo_limoneux",
    "limon-argileux": "limon_argileux",
    "limoneux": "limoneux",
    "sableux": "sableux",
    "sablo-limoneux": "sablo_limoneux",
}

# (nom, texture, rétention mm, pH, conductivité mm/h, densité g/cm³)
ROWS = [
    ("Argileux", "argileux", 200, 7.8, 1, 1.2),
    ("Argilo-limoneux", "argilo-limoneux", 170, 7.5, 2, 1.3),
    ("Limon argileux", "limon-argileux", 150, 7.2, 4, 1.35),
    ("Limoneux", "limoneux", 120, 7, 8, 1.4),
    ("Sableux", "sableux", 60, 6.5, 25, 1.6),
    ("Sablo-limoneux", "sablo-limoneux", 85, 6.8, 15, 1.5),
    ("Sol alluvial", "limoneux", 160, 7, 5, 1.4),
    ("Sol argileux", "argileux", 200, 7.5, 1.5, 1.25),
    ("Sol argilo-limoneux", "argilo-limoneux", 185, 7.3, 2.5, 1.3),
    ("Sol argilo-sableux", "argileux", 160, 7, 4, 1.35),
    ("Sol brun méditerranéen", "limon-argileux", 150, 7.5, 3.5, 1.35),
    ("Sol calcaire", "limoneux", 120, 8, 5, 1.45),
    ("Sol calcaire argileux", "argilo-limoneux", 155, 8.2, 2, 1.3),
    ("Sol calcaire caillouteux", "sablo-limoneux", 80, 8, 15, 1.5),
    ("Sol humifère", "limoneux", 180, 6.2, 4, 1.2),
    ("Sol limoneux", "limoneux", 140, 7, 6, 1.4),
    ("Sol limono-argileux", "limon-argileux", 170, 7.2, 3.5, 1.35),
    ("Sol limono-sableux", "sablo-limoneux", 110, 6.8, 10, 1.45),
    ("Sol sableux", "sableux", 60, 6.5, 25, 1.65),
    ("Sol sablo-limoneux", "sablo-limoneux", 90, 6.8, 12, 1.55),
    ("Sol salé (halomorphe)", "argileux", 130, 8.5, 2, 1.4),
    ("Sol tourbeux", "limoneux", 250, 5.5, 2, 0.9),
    ("Sol volcanique (andosol)", "limoneux", 220, 6, 3, 0.85),
    ("Terra rossa", "argilo-limoneux", 160, 7.8, 2.5, 1.3),
]


def seed(apps, schema_editor):
    TypeSol = apps.get_model("agronomie", "TypeSol")
    if TypeSol.objects.exists():
        return
    TypeSol.objects.bulk_create([
        TypeSol(
            nom=nom, texture=TEX[tex],
            capacite_retention_mm=ret, ph_typique=ph,
            conductivite_hydraulique=cond, densite_apparente=dens,
        )
        for (nom, tex, ret, ph, cond, dens) in ROWS
    ])


def unseed(apps, schema_editor):
    TypeSol = apps.get_model("agronomie", "TypeSol")
    TypeSol.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("agronomie", "0003_seed_culture_kc"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
