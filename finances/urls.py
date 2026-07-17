from django.urls import path

from . import exports, views

app_name = "finances"

urlpatterns = [
    path("charges/", views.charges, name="charges"),
    path("charges/nouvelle/", views.charge_create, name="charge_create"),
    path("revenus/nouveau/", views.revenu_create, name="revenu_create"),
    path("bilan-economique/", views.bilan_economique, name="bilan_economique"),
    path("facturation/", views.facturation, name="facturation"),
    path("reports/pdf/", exports.report_pdf, name="report_pdf"),
    path("reports/csv/", exports.report_csv, name="report_csv"),
]
