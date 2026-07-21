"""Calendrier de semis Kokopelli (Janvier→Mars) : renseigne / étend la période
de semis de chaque culture. Fusionne « sous abri » et « pleine terre » par mois."""

import unicodedata

from django.db import migrations

# Noms lisibles par mois (union sous abri + pleine terre). 1=Janvier, 2=Février, 3=Mars.
JAN = [
    "Bupleurum", "Carottes", "Cerfeuils", "Choux raves", "Coreopsis", "Épinard vivace",
    "Épinards", "Eupatoire", "Hélénie", "Laitues", "Mâches", "Navets", "Oignons", "Orges", "Poireau",
]
FEV = [
    "Amsonia", "Andrographis", "Argemone", "Artichauts", "Asclepias", "Asperules", "Asters",
    "Astragales", "Aubergines", "Aubergines amères", "Baptisia", "Belladone", "Betteraves",
    "Bupleurum", "Carottes", "Céleri à côte", "Céleri à couper", "Céleri rave", "Cerfeuils",
    "Choux brocolis", "Choux cabus", "Choux de Bruxelles", "Choux fleurs", "Choux raves",
    "Choux rouges", "Ciboules", "Consoude", "Coquelicots de Californie", "Coreopsis", "Coriandres",
    "Côtes de blette", "Cotons", "Eclipta", "Épinard vivace", "Épinards", "Millepertuis", "Mimulus",
    "Molucelles", "Navets", "Œillets", "Oignons", "Orges", "Orlaya", "Oseilles", "Pavots", "Persil",
    "Physalis", "Piments/Poivrons", "Poireau", "Pyrèthres", "Radis", "Salpiglossis", "Sauge", "Sida",
    "Silphium", "Stylophorum", "Tomates", "Tomates cerises", "Trachymene", "Tribulus", "Veronique",
    "Withania", "Avoine", "Cerfeuils tubéreux", "Fèves", "Lupin doux", "Pois", "Pois chiches",
]
MARS = [
    "Achillée", "Agastaches", "Agripaumes", "Amarante à feuille", "Amarante à grain", "Ammi",
    "Amorpha", "Amsonia", "Artichauts", "Asclepias", "Asperules", "Asters", "Asters de Chine",
    "Astragales", "Aubergines", "Aubergines amères", "Aunée", "Baptisia", "Baselles", "Basilics",
    "Basilics Tulsis", "Belladone", "Belles de jour", "Belles de nuit", "Betteraves", "Bleuet",
    "Bourraches", "Bupleurum", "Camomille", "Cannabis", "Capucines", "Carottes", "Céleri à côte",
    "Céleri à couper", "Céleri rave", "Celosia", "Centratherum", "Cerfeuils", "Chardon",
    "Chénopodes", "Chicorées", "Choux boux frisés / Kales", "Choux raves", "Choux rouges",
    "Chrysanthèmes", "Ciboules", "Ciboulettes", "Cléomes", "Clitoria", "Codonopsis", "Coloquintes",
    "Concombre", "Concombre sauteur", "Consoude", "Coquelicots de Californie", "Coreopsis",
    "Coriandres", "Cornichons", "Cosmos", "Côtes de blette", "Cotons", "Courge cireuse",
    "Courge de Siam", "Courges argyrosperma", "Courges en mélange", "Courges maxima",
    "Courges moschata", "Courges pepo", "Courgettes", "Cresson de Pará", "Cyclanthères", "Dahlias",
    "Daturas", "Épazote", "Épinard vivace", "Eupatoire", "Fenouil", "Ficoïde", "Gaillardes",
    "Gazania", "Gombos", "Gourdes", "Gueules de loup", "Hélénie", "Helianthe", "Hibiscus", "Hysope",
    "Iberis", "Immortelles", "Ipomée", "Jaborosa", "Kiwano", "Laitues", "Laitues asperge",
    "Leonotis", "Liatris", "Livèche", "Lobelia", "Luffas", "Lupin", "Lupin doux", "Mâches",
    "Marguerite", "Marguerite africaine", "Marjolaine", "Mauves", "Mélisse", "Melons", "Monardes",
    "Morelles", "Navets", "Nepeta", "Nielle des blés", "Œillets", "Œnothère", "Oignons", "Orges",
    "Origan", "Orlaya", "Ortie", "Oseilles", "Pastèques", "Pavots", "Périllas", "Persil", "Physalis",
    "Piments/Poivrons", "Poireau", "Pois de cœur", "Portulaca", "Proboscidea", "Pycnanthemum",
    "Pyrèthres", "Quinoas", "Radis", "Ratibida", "Réglisse", "Ricins", "Roses trémières",
    "Rudbeckia", "Salpiglossis", "Sarriettes", "Sauge", "Scabieuse", "Tabac", "Tagète", "Talinum",
    "Thym", "Tomates", "Tomates cerises", "Tournesol à fleur", "Tournesol mexicain",
    "Tournesols à grains", "Trachymene", "Tribulus", "Valeriana", "Vernonia", "Veronique",
    "Verveine", "Withania", "Zinnia", "Amourette", "Ancolies", "Angélique", "Arroches", "Cameline",
    "Cardère", "Chélidoine", "Choux chinois", "Choux rutabaga", "Coquelicots", "Luzerne",
    "Mélange d'engrais verts", "Mélanges de fleurs", "Mélanges mellifères", "Mélilot",
    "Mescluns Kokopelli", "Moutarde", "Moutarde indienne", "Moutarde japonaise", "Nigelles",
    "Panais", "Persil tubéreux", "Phacélies", "Pimprenelle", "Plantains", "Reseda", "Riz",
    "Roquette", "Salsifis", "Scorsonères", "Stellaire", "Trèfle", "Vesce",
]

# Heuristique de catégorie pour les nouvelles espèces créées.
LEGUMES = {
    "carotte", "navet", "betterave", "oignon", "poireau", "radi", "epinard", "aubergine", "tomate",
    "tomate cerise", "piment/poivron", "concombre", "cornichon", "courgette", "courge cireuse",
    "courge de siam", "courge argyrosperma", "courge en melange", "courge maxima", "courge moschata",
    "courge pepo", "melon", "pastEque", "pasteque", "artichaut", "chou rave", "chou cabu",
    "chou de bruxelle", "chou fleur", "chou rouge", "chou brocoli", "chou chinoi", "chou rutabaga",
    "choux boux frise / kale", "celeri a cote", "celeri a couper", "celeri rave", "cote de blette",
    "fenouil", "fEve", "feve", "poi", "poi chiche", "panai", "salsifi", "scorsonEre", "scorsonere",
    "cardon", "chicoree", "mache", "laitue", "laitue asperge", "roquette", "cresson de para",
    "gombo", "kiwano", "quinoa", "baselle", "oseille", "mesclun kokopelli", "ciboule", "ciboulette",
}
AROMATES = {
    "cerfeuil", "cerfeuil tubereux", "persil", "persil tubereux", "coriandre", "basilic",
    "basilic tulsi", "sauge", "thym", "origan", "marjolaine", "melisse", "livEche", "liveche",
    "sarriette", "hysope", "camomille", "nepeta", "menthe", "aneth", "pimprenelle", "epazote",
}
CEREALES = {"orge", "avoine", "riz", "mai", "amarante a grain"}


def _norm(name):
    text = unicodedata.normalize("NFKD", name).strip().lower()
    text = "".join(c for c in text if not unicodedata.combining(c))
    while text and text[-1] in "sx":  # pluriel simple
        text = text[:-1]
    return text.strip()


def _categorie(norm):
    if norm in CEREALES:
        return "cereales"
    if norm in LEGUMES:
        return "legumes"
    if norm in AROMATES:
        return "maraichage"
    return "autre"


def seed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")

    # nom d'origine → set de mois
    months = {}
    for m, names in ((1, JAN), (2, FEV), (3, MARS)):
        for name in names:
            months.setdefault(name, set()).add(m)

    # index des cultures existantes par nom normalisé
    existing = {}
    for c in CultureKc.objects.all():
        existing.setdefault(_norm(c.nom), c)

    for name, mset in months.items():
        lo, hi = min(mset), max(mset)
        norm = _norm(name)
        obj = existing.get(norm)
        if obj:
            # étend la fenêtre de semis existante
            obj.semis_debut = min(obj.semis_debut, lo) if obj.semis_debut else lo
            obj.semis_fin = max(obj.semis_fin, hi) if obj.semis_fin else hi
            obj.save(update_fields=["semis_debut", "semis_fin"])
        else:
            obj = CultureKc.objects.create(
                nom=name, categorie=_categorie(norm),
                semis_debut=lo, semis_fin=hi, source="Kokopelli / calendrier",
            )
            existing[norm] = obj


def unseed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    CultureKc.objects.filter(source="Kokopelli / calendrier").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("agronomie", "0012_remove_culturekc_arrosage_and_more"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
