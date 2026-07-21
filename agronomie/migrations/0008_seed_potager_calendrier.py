"""Enrichit la base de cultures avec un jeu potager (esprit kokopelli-semences)
et renseigne les périodes de semis / récolte (calendrier potager français).
"""

from django.db import migrations

# (nom, nom scientifique, catégorie, kc_i, kc_m, kc_e, semis_debut, semis_fin, recolte_debut, recolte_fin)
POTAGER = [
    ("Tomate", "Solanum lycopersicum", "legumes", 0.6, 1.15, 0.80, 3, 4, 7, 10),
    ("Aubergine", "Solanum melongena", "legumes", 0.6, 1.05, 0.90, 2, 4, 7, 10),
    ("Poivron", "Capsicum annuum", "legumes", 0.6, 1.05, 0.90, 2, 4, 7, 10),
    ("Piment", "Capsicum annuum", "legumes", 0.6, 1.05, 0.90, 2, 4, 7, 10),
    ("Courgette", "Cucurbita pepo", "legumes", 0.6, 1.15, 0.80, 4, 6, 6, 10),
    ("Concombre", "Cucumis sativus", "legumes", 0.6, 1.00, 0.75, 4, 5, 7, 9),
    ("Courge", "Cucurbita maxima", "legumes", 0.5, 1.00, 0.80, 4, 5, 9, 11),
    ("Potiron", "Cucurbita maxima", "legumes", 0.5, 1.00, 0.80, 4, 5, 9, 11),
    ("Melon", "Cucumis melo", "fruits", 0.5, 1.05, 0.75, 3, 5, 7, 9),
    ("Pastèque", "Citrullus lanatus", "fruits", 0.4, 1.00, 0.75, 3, 5, 7, 9),
    ("Haricot", "Phaseolus vulgaris", "legumes", 0.5, 1.05, 0.90, 5, 7, 7, 10),
    ("Pois", "Pisum sativum", "legumes", 0.5, 1.15, 1.10, 2, 4, 5, 7),
    ("Fève", "Vicia faba", "legumes", 0.5, 1.15, 1.10, 10, 3, 5, 7),
    ("Carotte", "Daucus carota", "legumes", 0.5, 1.05, 0.95, 3, 7, 6, 11),
    ("Betterave", "Beta vulgaris", "legumes", 0.5, 1.05, 0.95, 4, 6, 7, 10),
    ("Radis", "Raphanus sativus", "legumes", 0.7, 0.90, 0.85, 3, 9, 4, 10),
    ("Navet", "Brassica rapa", "legumes", 0.5, 1.05, 0.95, 7, 9, 10, 12),
    ("Panais", "Pastinaca sativa", "legumes", 0.5, 1.05, 0.95, 3, 5, 10, 2),
    ("Poireau", "Allium porrum", "legumes", 0.7, 1.00, 0.98, 2, 4, 9, 3),
    ("Oignon", "Allium cepa", "legumes", 0.5, 1.05, 0.80, 2, 4, 7, 9),
    ("Ail", "Allium sativum", "legumes", 0.5, 1.00, 0.70, 10, 12, 6, 7),
    ("Échalote", "Allium cepa var. aggregatum", "legumes", 0.5, 1.00, 0.70, 10, 3, 6, 8),
    ("Laitue", "Lactuca sativa", "maraichage", 0.7, 1.00, 0.95, 2, 9, 5, 11),
    ("Mâche", "Valerianella locusta", "maraichage", 0.7, 1.00, 0.95, 8, 10, 10, 3),
    ("Roquette", "Eruca sativa", "maraichage", 0.7, 1.00, 0.95, 3, 9, 4, 11),
    ("Épinard", "Spinacia oleracea", "maraichage", 0.7, 1.00, 0.95, 3, 9, 5, 11),
    ("Blette", "Beta vulgaris subsp. cicla", "legumes", 0.7, 1.00, 0.95, 3, 7, 6, 11),
    ("Chou pommé", "Brassica oleracea", "legumes", 0.7, 1.05, 0.95, 3, 6, 9, 2),
    ("Chou-fleur", "Brassica oleracea var. botrytis", "legumes", 0.7, 1.05, 0.95, 4, 6, 9, 11),
    ("Brocoli", "Brassica oleracea var. italica", "legumes", 0.7, 1.05, 0.95, 4, 6, 8, 11),
    ("Céleri", "Apium graveolens", "legumes", 0.5, 1.05, 0.95, 3, 4, 8, 11),
    ("Fenouil", "Foeniculum vulgare", "legumes", 0.5, 1.00, 0.95, 4, 7, 8, 11),
    ("Basilic", "Ocimum basilicum", "maraichage", 0.6, 1.00, 0.80, 3, 6, 6, 10),
    ("Persil", "Petroselinum crispum", "maraichage", 0.6, 1.00, 0.85, 3, 8, 5, 11),
    ("Coriandre", "Coriandrum sativum", "maraichage", 0.6, 1.00, 0.80, 3, 9, 5, 11),
    ("Ciboulette", "Allium schoenoprasum", "maraichage", 0.6, 1.00, 0.85, 3, 5, 5, 10),
    ("Pomme de terre", "Solanum tuberosum", "legumes", 0.5, 1.15, 0.75, 3, 5, 6, 9),
    ("Artichaut", "Cynara scolymus", "legumes", 0.5, 1.00, 0.95, 3, 4, 5, 9),
    ("Maïs doux", "Zea mays", "cereales", 0.3, 1.15, 1.05, 4, 6, 8, 10),
]


def seed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    for nom, sci, cat, ki, km, ke, sd, sf, rd, rf in POTAGER:
        defaults = {
            "nom_scientifique": sci, "categorie": cat,
            "kc_initial": ki, "kc_mid": km, "kc_end": ke,
            "semis_debut": sd, "semis_fin": sf, "recolte_debut": rd, "recolte_fin": rf,
            "source": "Kokopelli / calendrier potager",
        }
        existing = CultureKc.objects.filter(nom=nom).first()
        if existing:
            # Ne renseigne que le calendrier + le scientifique s'ils manquent (respecte les Kc déjà réglés).
            existing.semis_debut, existing.semis_fin = sd, sf
            existing.recolte_debut, existing.recolte_fin = rd, rf
            if not existing.nom_scientifique:
                existing.nom_scientifique = sci
            existing.save()
        else:
            CultureKc.objects.create(nom=nom, **defaults)


def unseed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    CultureKc.objects.filter(source="Kokopelli / calendrier potager").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("agronomie", "0007_culturekc_recolte_debut_culturekc_recolte_fin_and_more"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
