"""Fiche variété détaillée d'exemple (Aunt Ruby's German Green), type kokopelli."""

from django.db import migrations

NOM = "Aunt Ruby's German Green"
DATA = {
    "variete": NOM,
    "nom_scientifique": "Solanum lycopersicum",
    "categorie": "legumes",
    "note": 4.0,
    "nb_avis": 2,
    "description": (
        "Cette variété vigoureuse produit des fruits de type « chair de bœuf », de 250 à 500 g, "
        "vert clair teinté de jaune-rose. Ils renferment une chair dense et juteuse de saveur douce "
        "et ont une tendance à l'éclatement."
    ),
    "semis_debut": 2, "semis_fin": 4, "recolte_debut": 8, "recolte_fin": 10,
    "kc_initial": 0.6, "kc_mid": 1.15, "kc_end": 0.8,
    "exposition": "plein_soleil",
    "arrosage": "moyen",
    "nature_sol": "Tout type de sol",
    "sol_detail": "Drainé, riche, réchauffé",
    "mode_culture": "En pleine terre, en serre",
    "conseil_semis": (
        "Semer en godets, à une température comprise entre 16 et 20 °C, sous un abri bien lumineux, "
        "5 semaines avant la mise en place. Repiquer la motte entière en pleine terre, après les "
        "dernières gelées, à 50 cm de distance minimum, en enterrant la tige jusqu'aux premières "
        "feuilles. Arroser abondamment au moment de la plantation."
    ),
    "conseil_culture": (
        "Les Solanacées ont besoin de lumière et de chaleur pour produire. Dans les climats frais, "
        "il est préférable de les cultiver sous abri et, en fonction du sol, de prévoir un arrosage régulier."
    ),
    "poids": "De 250 à 500 g",
    "contenance_sachet": "35 graines",
    "forme": "Aplatie",
    "texture_fruit": "Ferme",
    "type_croissance": "Indéterminée",
    "couleur": "Vert",
    "feuillage": "Pomme de terre",
    "type_semis": "En godet",
    "origine": "Allemagne",
    "origine_texte": (
        "Cette variété de famille, originaire d'Allemagne, a été transmise par Ruby Arnold "
        "de Greeneville dans le Tennessee."
    ),
    "source": "Kokopelli",
}


def seed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    obj = CultureKc.objects.filter(nom=NOM).first()
    if obj:
        for k, v in DATA.items():
            setattr(obj, k, v)
        obj.save()
    else:
        CultureKc.objects.create(nom=NOM, **DATA)


def unseed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    CultureKc.objects.filter(nom=NOM).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("agronomie", "0010_culturekc_arrosage_culturekc_conseil_culture_and_more"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
