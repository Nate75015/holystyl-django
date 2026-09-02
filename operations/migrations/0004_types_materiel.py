"""Fait passer le matériel existant au vocabulaire partagé.

`Machine` et `CatalogueEngin` avaient chacun son énumération, et elles ne
disaient pas la même chose : « tractor » ici, « tracteur » là. Les deux tables
rejoignent la liste de `operations.materiel`.

Deux reprises élargissent le sens plutôt que de le conserver à l'identique,
faute d'équivalent exact dans l'ancienne liste : un « semoir » sans plus de
précision devient un semoir en ligne, un « épandeur » un épandeur d'engrais.
Ce sont les lectures les plus courantes ; une fiche mal rangée se corrige
depuis la page du parc.
"""

from django.db import migrations

MACHINE = {
    "pump": "pompe",
    "tractor": "tracteur_standard",
    "enrouleur": "enrouleur",
    "pivot": "pivot",
    "sprayer": "pulverisateur",
    "other": "autre",
}

CATALOGUE = {
    "tracteur": "tracteur_standard",
    "pulverisateur": "pulverisateur",
    "semoir": "semoir_ligne",
    "epandeur": "epandeur_engrais",
    "moissonneuse": "moissonneuse_batteuse",
    "charrue": "charrue",
    "cultivateur": "cultivateur",
    "benne": "benne",
    "pompe": "pompe",
    "autre": "autre",
}


def _appliquer(modele, table):
    for ancien, nouveau in table.items():
        if ancien != nouveau:
            modele.objects.filter(type=ancien).update(type=nouveau)


def _renverser(modele, table, defaut):
    """Retour en arrière : ce que l'ancienne liste ne savait pas dire devient « autre ».

    L'ordre compte. On replie d'abord les types nés du nouveau vocabulaire —
    une herse étrille n'a pas d'ancien code — puis on rend leur nom d'origine
    à ceux qui en avaient un.
    """
    retour = {}
    for ancien, nouveau in table.items():
        retour.setdefault(nouveau, ancien)
    modele.objects.exclude(type__in=set(retour)).update(type=defaut)
    for nouveau, ancien in retour.items():
        if ancien != nouveau:
            modele.objects.filter(type=nouveau).update(type=ancien)


def avancer(apps, schema_editor):
    _appliquer(apps.get_model("operations", "Machine"), MACHINE)
    _appliquer(apps.get_model("operations", "CatalogueEngin"), CATALOGUE)


def reculer(apps, schema_editor):
    _renverser(apps.get_model("operations", "Machine"), MACHINE, "other")
    _renverser(apps.get_model("operations", "CatalogueEngin"), CATALOGUE, "autre")


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0003_alter_catalogueengin_type_alter_machine_type_and_more"),
    ]

    operations = [
        migrations.RunPython(avancer, reculer),
    ]
