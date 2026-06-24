"""Seed du référentiel CultureKc — coefficients culturaux FAO-56 (+ ARVALIS)."""

from django.db import migrations

# (nom, nom_scientifique, catégorie, kc_initial, kc_mid, kc_end, source)
CAT = {
    "Céréales": "cereales",
    "Légumes": "legumes",
    "Fruits": "fruits",
    "Vigne": "vigne",
    "Oléagineux": "oleagineux",
    "Fourrage": "fourrage",
    "Maraîchage": "maraichage",
}

ROWS = [
    ("Abricotier", "Prunus armeniaca", "Fruits", 0.45, 1.00, 0.65, "FAO-56"),
    ("Agrumes (citron)", "Citrus limon", "Fruits", 0.75, 0.85, 0.75, "FAO-56"),
    ("Agrumes (orange)", "Citrus sinensis", "Fruits", 0.75, 0.85, 0.75, "FAO-56"),
    ("Ail", "Allium sativum", "Légumes", 0.70, 1.00, 0.70, "FAO-56"),
    ("Amandier", "Prunus dulcis", "Fruits", 0.40, 0.90, 0.65, "FAO-56"),
    ("Artichaut", "Cynara cardunculus", "Maraîchage", 0.50, 1.00, 0.95, "FAO-56"),
    ("Aubergine", "Solanum melongena", "Légumes", 0.60, 1.05, 0.90, "FAO-56"),
    ("Basilic", "Ocimum basilicum", "Maraîchage", 0.60, 1.10, 0.90, "FAO-56"),
    ("Blé dur", "Triticum durum", "Céréales", 0.30, 1.15, 0.40, "FAO-56/ARVALIS"),
    ("Blé dur", "Triticum durum", "Céréales", 0.30, 1.15, 0.25, "FAO-56"),
    ("Blé tendre", "Triticum aestivum", "Céréales", 0.30, 1.15, 0.25, "FAO-56"),
    ("Blé tendre", "Triticum aestivum", "Céréales", 0.30, 1.15, 0.40, "FAO-56/ARVALIS"),
    ("Brocoli", "Brassica oleracea", "Maraîchage", 0.70, 1.05, 0.95, "FAO-56"),
    ("Carotte", "Daucus carota", "Légumes", 0.70, 1.05, 0.95, "FAO-56"),
    ("Carotte", "Daucus carota", "Légumes", 0.70, 1.05, 0.95, "FAO-56"),
    ("Cerisier", "Prunus avium", "Fruits", 0.45, 1.00, 0.65, "FAO-56"),
    ("Chou-fleur", "Brassica oleracea", "Maraîchage", 0.70, 1.05, 0.95, "FAO-56"),
    ("Colza", "Brassica napus", "Oléagineux", 0.35, 1.10, 0.35, "FAO-56"),
    ("Colza", "Brassica napus", "Oléagineux", 0.35, 1.10, 0.35, "FAO-56/ARVALIS"),
    ("Concombre", "Cucumis sativus", "Légumes", 0.60, 1.00, 0.75, "FAO-56"),
    ("Courgette", "Cucurbita pepo", "Maraîchage", 0.50, 1.00, 0.80, "FAO-56"),
    ("Courgette", "Cucurbita pepo", "Légumes", 0.50, 0.95, 0.75, "FAO-56"),
    ("Épinard", "Spinacia oleracea", "Maraîchage", 0.70, 1.00, 0.95, "FAO-56"),
    ("Fenouil", "Foeniculum vulgare", "Maraîchage", 0.50, 1.05, 0.90, "FAO-56"),
    ("Figuier", "Ficus carica", "Fruits", 0.50, 1.05, 0.70, "FAO-56"),
    ("Fraisier", "Fragaria x ananassa", "Fruits", 0.40, 0.85, 0.75, "FAO-56"),
    ("Grenadier", "Punica granatum", "Fruits", 0.40, 1.05, 0.65, "FAO-56"),
    ("Haricot vert", "Phaseolus vulgaris", "Légumes", 0.50, 1.05, 0.90, "FAO-56"),
    ("Haricot vert", "Phaseolus vulgaris", "Légumes", 0.40, 1.05, 0.90, "FAO-56"),
    ("Kiwi", "Actinidia deliciosa", "Fruits", 0.40, 1.05, 1.05, "FAO-56"),
    ("Laitue", "Lactuca sativa", "Légumes", 0.70, 1.00, 0.95, "FAO-56"),
    ("Lentille", "Lens culinaris", "Légumes", 0.40, 1.10, 0.30, "FAO-56"),
    ("Luzerne", "Medicago sativa", "Fourrage", 0.40, 1.20, 1.15, "FAO-56"),
    ("Luzerne", "Medicago sativa", "Fourrage", 0.40, 1.20, 1.15, "FAO-56"),
    ("Maïs fourrage", "Zea mays", "Fourrage", 0.30, 1.20, 0.35, "FAO-56"),
    ("Maïs fourrage", "Zea mays", "Fourrage", 0.30, 1.20, 1.05, "FAO-56/ARVALIS"),
    ("Maïs grain", "Zea mays", "Céréales", 0.30, 1.20, 0.35, "FAO-56"),
    ("Maïs grain", "Zea mays", "Céréales", 0.30, 1.20, 0.60, "FAO-56/ARVALIS"),
    ("Melon", "Cucumis melo", "Légumes", 0.50, 1.05, 0.75, "FAO-56"),
    ("Melon", "Cucumis melo", "Maraîchage", 0.50, 1.05, 0.75, "FAO-56"),
    ("Oignon", "Allium cepa", "Légumes", 0.70, 1.05, 0.75, "FAO-56"),
    ("Oignon", "Allium cepa", "Légumes", 0.70, 1.05, 0.75, "FAO-56"),
    ("Olivier", "Olea europaea", "Fruits", 0.65, 0.70, 0.65, "FAO-56"),
    ("Orge", "Hordeum vulgare", "Céréales", 0.30, 1.15, 0.25, "FAO-56"),
    ("Orge", "Hordeum vulgare", "Céréales", 0.30, 1.15, 0.25, "FAO-56/ARVALIS"),
    ("Pastèque", "Citrullus lanatus", "Légumes", 0.40, 1.00, 0.75, "FAO-56"),
    ("Pêcher", "Prunus persica", "Fruits", 0.45, 1.20, 0.95, "FAO-56"),
    ("Pêcher", "Prunus persica", "Fruits", 0.45, 1.10, 0.65, "FAO-56"),
    ("Persil", "Petroselinum crispum", "Maraîchage", 0.60, 1.05, 1.00, "FAO-56"),
    ("Poirier", "Pyrus communis", "Fruits", 0.45, 1.20, 0.85, "FAO-56"),
    ("Pois chiche", "Cicer arietinum", "Légumes", 0.40, 1.00, 0.35, "FAO-56"),
    ("Poivron", "Capsicum annuum", "Légumes", 0.60, 1.05, 0.90, "FAO-56"),
    ("Pomme de terre", "Solanum tuberosum", "Légumes", 0.50, 1.15, 0.75, "FAO-56/ARVALIS"),
    ("Pomme de terre", "Solanum tuberosum", "Légumes", 0.50, 1.15, 0.75, "FAO-56"),
    ("Pommier", "Malus domestica", "Fruits", 0.45, 1.20, 0.95, "FAO-56"),
    ("Pommier", "Malus domestica", "Fruits", 0.45, 1.20, 0.85, "FAO-56"),
    ("Ray-grass", "Lolium perenne", "Fourrage", 0.95, 1.05, 1.00, "FAO-56"),
    ("Ray-grass", "Lolium perenne", "Fourrage", 0.95, 1.05, 1.00, "FAO-56"),
    ("Riz", "Oryza sativa", "Céréales", 1.05, 1.20, 0.75, "FAO-56"),
    ("Salade (laitue)", "Lactuca sativa", "Maraîchage", 0.70, 1.00, 0.95, "FAO-56"),
    ("Soja", "Glycine max", "Oléagineux", 0.40, 1.15, 0.50, "FAO-56"),
    ("Soja", "Glycine max", "Oléagineux", 0.40, 1.15, 0.50, "FAO-56"),
    ("Sorgho", "Sorghum bicolor", "Céréales", 0.30, 1.00, 0.55, "FAO-56"),
    ("Sorgho grain", "Sorghum bicolor", "Céréales", 0.30, 1.00, 0.55, "FAO-56"),
    ("Tomate", "Solanum lycopersicum", "Légumes", 0.60, 1.15, 0.70, "FAO-56"),
    ("Tomate", "Solanum lycopersicum", "Légumes", 0.60, 1.15, 0.80, "FAO-56"),
    ("Tournesol", "Helianthus annuus", "Oléagineux", 0.35, 1.10, 0.35, "FAO-56"),
    ("Tournesol", "Helianthus annuus", "Oléagineux", 0.35, 1.00, 0.35, "FAO-56/ARVALIS"),
    ("Triticale", "Triticosecale", "Céréales", 0.30, 1.15, 0.40, "ARVALIS"),
    ("Vigne (raisin de cuve)", "Vitis vinifera", "Vigne", 0.30, 0.85, 0.45, "FAO-56/ARVALIS"),
    ("Vigne (raisin de cuve)", "Vitis vinifera", "Vigne", 0.30, 0.70, 0.45, "FAO-56"),
    ("Vigne (raisin de table)", "Vitis vinifera", "Vigne", 0.30, 0.85, 0.45, "FAO-56"),
    ("Vigne (raisin de table)", "Vitis vinifera", "Vigne", 0.30, 0.85, 0.45, "FAO-56"),
]


def seed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    if CultureKc.objects.exists():
        return  # ne pas re-seeder si des données existent déjà
    CultureKc.objects.bulk_create([
        CultureKc(
            nom=nom, nom_scientifique=sci, categorie=CAT[cat],
            kc_initial=ki, kc_mid=km, kc_end=ke, source=src,
        )
        for (nom, sci, cat, ki, km, ke, src) in ROWS
    ])


def unseed(apps, schema_editor):
    CultureKc = apps.get_model("agronomie", "CultureKc")
    CultureKc.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("agronomie", "0002_fertigation"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
