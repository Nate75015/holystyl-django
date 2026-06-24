from django.urls import path

from . import views

app_name = "pac"

urlpatterns = [
    path("pac/", views.pac, name="pac"),
    path("pac/ajouter/", views.pac_create, name="create"),
    path("pac/<int:pk>/supprimer/", views.pac_delete, name="delete"),
]
