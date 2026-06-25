from django.urls import path

from . import views

app_name = "environnement"

urlpatterns = [
    path("environnement/biodiversite/", views.biodiversite, name="biodiversite"),
    path("environnement/bilan-eau/", views.bilan_eau, name="bilan_eau"),
    path("environnement/bilan-eau/export/", views.bilan_eau_export, name="bilan_eau_export"),
    path("environnement/bilan-azote/", views.bilan_azote, name="bilan_azote"),
    path("environnement/empreinte-carbone/", views.empreinte_carbone, name="empreinte_carbone"),
    path("environnement/rapport/", views.rapport_environnemental, name="rapport"),
    path("environnement/sante-vegetale/", views.sante_vegetale, name="sante_vegetale"),
    path("environnement/taxonomie/", views.taxonomie, name="taxonomie"),
    path("environnement/taxonomie/ajouter/", views.taxonomie_create, name="taxonomie_create"),
    path("environnement/taxonomie/<int:pk>/supprimer/", views.taxonomie_delete, name="taxonomie_delete"),
]
