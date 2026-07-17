from django.contrib import admin

from .models import AnalyseSol, DemandeAnalyse, Laboratoire


@admin.register(AnalyseSol)
class AnalyseSolAdmin(admin.ModelAdmin):
    list_display = ("parcelle", "date", "ph", "matiere_organique", "laboratoire")
    list_filter = ("laboratoire",)
    search_fields = ("parcelle__name", "laboratoire", "numero_laboratoire", "reference")
    raw_id_fields = ("exploitation", "parcelle")
    fieldsets = (
        (None, {"fields": ("exploitation", "parcelle", "date", "document", "notes")}),
        ("Identification (labo)", {"fields": (
            "laboratoire", "numero_laboratoire", "reference", "technicien", "commune",
            "profondeur_prelevement", "date_prelevement", "date_arrivee_labo", "date_expedition",
        )}),
        ("pH & calcaire", {"fields": (
            "ph", "ph_kcl", "ec", "calcaire_total", "calcaire_actif", "calcium_cao",
        )}),
        ("MO, carbone & azote", {"fields": (
            "matiere_organique", "carbone_organique", "azote_total", "c_n",
            "coefficient_k2", "azote_ammoniacal",
        )}),
        ("Éléments majeurs", {"fields": (
            "phosphore_assimilable", "phosphore_olsen", "potassium_echangeable",
            "magnesium_mgo", "sodium_na2o",
        )}),
        ("Oligo-éléments", {"fields": ("bore", "cuivre", "fer", "manganese", "zinc")}),
        ("CEC & équilibre cationique", {"fields": (
            "cec", "taux_saturation", "ca_cec", "k_cec", "mg_cec", "na_cec", "h_cec",
        )}),
        ("Granulométrie / texture", {"fields": (
            "type_sol", "argile", "limons_fins", "limons_grossiers",
            "sables_fins", "sables_grossiers",
        )}),
        ("Propriétés physiques & réserve en eau", {"fields": (
            "humidite", "matiere_seche", "refus_2mm", "densite_apparente",
            "reserve_utile", "reserve_facilement_utilisable", "capacite_retention_pf25",
            "capacite_retention_pf42", "indice_battance", "risque_battance",
        )}),
        ("Éléments traces métalliques", {"fields": (
            "cadmium", "chrome", "cuivre_total", "mercure", "nickel", "plomb", "zinc_total",
            "arsenic", "cobalt", "molybdene", "selenium", "fer_total", "manganese_total",
            "bore_total", "aluminium_echangeable", "aluminium_total",
        )}),
        ("Contaminants organiques (annexe)", {"fields": ("somme_16_hap", "somme_7_pcb")}),
    )


@admin.register(Laboratoire)
class LaboratoireAdmin(admin.ModelAdmin):
    list_display = ("nom", "region", "specialites", "delai_jours", "actif")
    list_filter = ("actif", "region")
    search_fields = ("nom", "region", "specialites")


@admin.register(DemandeAnalyse)
class DemandeAnalyseAdmin(admin.ModelAdmin):
    list_display = ("parcelle", "laboratoire", "type_analyse", "statut", "created_at")
    list_filter = ("statut", "type_analyse", "laboratoire")
    search_fields = ("parcelle__name", "laboratoire__nom")
    raw_id_fields = ("exploitation", "parcelle", "user", "analyse")
