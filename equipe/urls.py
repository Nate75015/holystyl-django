from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("equipe/", views.equipe, name="equipe"),
    path("equipe/<int:pk>/modifier/", views.membre_edit, name="membre_edit"),
    path("taches/", views.taches, name="taches"),
    path("taches/<int:pk>/modifier/", views.taches_edit, name="taches_edit"),
    path("localisation/<str:token>/", views.location_share, name="location_share"),
]
