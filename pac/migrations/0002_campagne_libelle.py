"""La campagne PAC passe de l'année entière au libellé partagé « 2025/2026 ».

Conversion en quatre temps plutôt qu'un ALTER avec cast : le passage
entier → texte n'est pas portable d'un moteur à l'autre.
"""

from django.db import migrations, models


def vers_libelle(apps, schema_editor):
    """2025 → « 2025/2026 » (campagne de septembre à septembre)."""
    AidePAC = apps.get_model("pac", "AidePAC")
    for aide in AidePAC.objects.all():
        annee = aide.campagne
        AidePAC.objects.filter(pk=aide.pk).update(
            campagne_libelle=f"{annee}/{annee + 1}" if annee else ""
        )


def vers_annee(apps, schema_editor):
    """Retour arrière : « 2025/2026 » → 2025."""
    AidePAC = apps.get_model("pac", "AidePAC")
    for aide in AidePAC.objects.all():
        debut = (aide.campagne_libelle or "").split("/")[0].strip()
        AidePAC.objects.filter(pk=aide.pk).update(campagne=int(debut) if debut.isdigit() else 0)


class Migration(migrations.Migration):

    dependencies = [("pac", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="aidepac",
            name="campagne_libelle",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(vers_libelle, vers_annee),
        migrations.RemoveField(model_name="aidepac", name="campagne"),
        migrations.RenameField(
            model_name="aidepac", old_name="campagne_libelle", new_name="campagne"
        ),
        migrations.AlterField(
            model_name="aidepac",
            name="campagne",
            field=models.CharField(
                help_text="Campagne agricole, ex. « 2025/2026 » (voir Mes parcelles › Campagnes).",
                max_length=20,
                verbose_name="campagne",
            ),
        ),
    ]
