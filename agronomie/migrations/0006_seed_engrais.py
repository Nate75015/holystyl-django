"""Seed du catalogue d'engrais (référentiel N/P/K)."""

from django.db import migrations

# (nom, type, N%, P%, K%, solubilité, effet pH)  — None pour « — »
ROWS = [
    ("Nitrate d'ammonium (33%)", "N", 33, None, None, "Très élevée", "Neutre"),
    ("Urée (46%)", "N", 46, None, None, "Élevée", "Légèrement acide"),
    ("Solution azotée UAN (32%)", "N", 32, None, None, "Liquide", "Neutre"),
    ("Acide phosphorique (75%)", "P", None, 75, None, "Liquide", "Acide"),
    ("MAP (12-61-0)", "NP", 12, 61, None, "Élevée", "Acide"),
    ("Nitrate de potassium (13-0-46)", "NK", 13, None, 46, "Élevée", "Neutre"),
    ("Chlorure de potassium (0-0-60)", "K", None, None, 60, "Élevée", "Neutre"),
    ("Sulfate de potassium (0-0-50)", "K", None, None, 50, "Modérée", "Légèrement acide"),
    ("NPK 15-15-15", "NPK", 15, 15, 15, "Élevée", "Neutre"),
    ("NPK 20-10-10", "NPK", 20, 10, 10, "Élevée", "Neutre"),
]


def seed(apps, schema_editor):
    Engrais = apps.get_model("agronomie", "Engrais")
    if Engrais.objects.exists():
        return
    Engrais.objects.bulk_create([
        Engrais(
            nom=nom, type_engrais=typ, n_pct=n, p_pct=p, k_pct=k,
            solubilite=sol, ph_effet=ph,
        )
        for (nom, typ, n, p, k, sol, ph) in ROWS
    ])


def unseed(apps, schema_editor):
    Engrais = apps.get_model("agronomie", "Engrais")
    Engrais.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("agronomie", "0005_engrais"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
