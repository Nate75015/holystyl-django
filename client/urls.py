from django.urls import path

from . import views

app_name = "client"

urlpatterns = [
    path("clients/", views.clients, name="clients"),
    # Les routes spécifiques d'abord : « partenaire » ne doit pas être pris pour un type.
    path("relations/partenaire/ajouter/", views.partenaire_create, name="partenaire_create"),
    path("relations/partenaire/<int:pk>/supprimer/", views.partenaire_delete, name="partenaire_delete"),
    path("relations/<str:type_partenaire>/", views.partenaires, name="partenaires"),
    path("clients/nouveau/", views.client_create, name="create"),
    path("clients/<int:pk>/", views.client_detail, name="detail"),
    path("clients/<int:pk>/modifier/", views.client_edit, name="edit"),
    path("clients/<int:pk>/supprimer/", views.client_delete, name="delete"),
]
