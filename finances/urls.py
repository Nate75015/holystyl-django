from django.urls import path

from . import exports, views

app_name = "finances"

urlpatterns = [
    path("charges/", views.charges, name="charges"),
    path("charges/nouvelle/", views.charge_create, name="charge_create"),
    path("revenus/nouveau/", views.revenu_create, name="revenu_create"),
    path("bilan-economique/", views.bilan_economique, name="bilan_economique"),
    path("facturation/", views.facturation, name="facturation"),
    path("fermage/", views.fermage, name="fermage"),
    path("fermage/indice/ajouter/", views.indice_fermage_add, name="indice_fermage_add"),
    path("fermage/indice/<int:pk>/supprimer/", views.indice_fermage_delete, name="indice_fermage_delete"),
    path("fermage/bail/<int:pk>/", views.bail_fermage_update, name="bail_fermage_update"),
    path("reports/pdf/", exports.report_pdf, name="report_pdf"),
    path("reports/csv/", exports.report_csv, name="report_csv"),
]
