from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("parc-materiel/", views.parc_materiel, name="parc_materiel"),
    path("parc-materiel/ajouter/", views.machine_create, name="machine_create"),
    path("parc-materiel/<int:pk>/supprimer/", views.machine_delete, name="machine_delete"),
]
