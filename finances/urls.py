from django.urls import path

from . import exports, views

app_name = "finances"

urlpatterns = [
    path("charges/", views.charges, name="charges"),
    path("charges/nouvelle/", views.charge_create, name="charge_create"),
    path("revenus/nouveau/", views.revenu_create, name="revenu_create"),
    path("bilan-economique/", views.bilan_economique, name="bilan_economique"),
    path("facturation/", views.facturation, name="facturation"),
    path("facturation/nouvelle/", views.facture_editeur, name="facture_editeur"),
    path("facturation/creer/", views.facture_create, name="facture_create"),
    path("facturation/<int:pk>/envoyer/", views.facture_envoyer, name="facture_envoyer"),
    path("facturation/<int:pk>/statut/", views.facture_statut, name="facture_statut"),
    path("facturation/<int:pk>/ubl/", views.facture_xml, name="facture_xml"),
    path("devis/", views.devis, name="devis"),
    path("devis/nouveau/", views.devis_editeur, name="devis_editeur"),
    path("devis/creer/", views.devis_create, name="devis_create"),
    path("devis/<int:pk>/statut/", views.devis_statut, name="devis_statut"),
    path("devis/<int:pk>/signature/", views.devis_signature, name="devis_signature"),
    path("devis/<int:pk>/convertir/", views.devis_convertir, name="devis_convertir"),
    path("fermage/", views.fermage, name="fermage"),
    path("fermage/indice/ajouter/", views.indice_fermage_add, name="indice_fermage_add"),
    path("fermage/indice/<int:pk>/supprimer/", views.indice_fermage_delete, name="indice_fermage_delete"),
    path("fermage/bail/<int:pk>/", views.bail_fermage_update, name="bail_fermage_update"),
    path("reports/pdf/", exports.report_pdf, name="report_pdf"),
    path("reports/csv/", exports.report_csv, name="report_csv"),
]
