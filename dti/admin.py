"""Administration des diagnostics reçus.

L'écran de rattachement destiné aux opérateurs viendra dans l'interface
métier ; l'admin sert ici à inspecter une réception — voir ce qui est arrivé,
pourquoi un import est en quarantaine, et ce que le rapport dit avoir créé.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (Canalisation, Composant, DtiImport, Equipement, MediaDti,
                     MesureDebit, MesureElectrique, RessourceEau)


@admin.register(DtiImport)
class DtiImportAdmin(admin.ModelAdmin):
    list_display = ("__str__", "statut", "exploitation", "schema_version",
                    "recu_le", "medias_recuperes")
    list_filter = ("statut", "schema_version", "source", "medias_recuperes")
    search_fields = ("siret_declare", "nom_declare", "empreinte")
    date_hierarchy = "recu_le"
    # Le payload et l'empreinte viennent de la source : les modifier ici
    # reviendrait à falsifier une pièce reçue.
    readonly_fields = ("empreinte", "payload", "rapport", "medias_archive",
                       "recu_le", "exported_at", "dti_source_id", "schema_version")

    @admin.display(description=_("en quarantaine"), boolean=True)
    def quarantaine(self, obj):
        return obj.en_quarantaine


class ElementDtiAdmin(admin.ModelAdmin):
    """Réglages communs : ces objets appartiennent à un import et se lisent
    toujours dans son contexte."""

    list_select_related = ("import_dti", "exploitation")
    readonly_fields = ("import_dti", "source_id")


@admin.register(RessourceEau)
class RessourceEauAdmin(ElementDtiAdmin):
    list_display = ("nom", "categorie", "exploitation", "debit_max_m3h", "import_dti")
    list_filter = ("categorie",)
    search_fields = ("nom", "commune", "cadastral_ref")


@admin.register(Canalisation)
class CanalisationAdmin(ElementDtiAdmin):
    list_display = ("__str__", "ordre", "materiau", "longueur_m", "exploitation")
    list_filter = ("materiau",)


@admin.register(Equipement)
class EquipementAdmin(ElementDtiAdmin):
    list_display = ("__str__", "type_equipement", "marque", "etat", "exploitation")
    list_filter = ("type_equipement", "categorie", "etat")
    search_fields = ("nom", "marque", "modele")


admin.site.register([Composant, MesureDebit, MesureElectrique, MediaDti])
