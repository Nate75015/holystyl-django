from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("equipe/", views.equipe, name="equipe"),
    path("taches/", views.taches, name="taches"),
    path("mes-taches/", views.mes_taches, name="mes_taches"),
    path("localisation/<str:token>/", views.location_share, name="location_share"),
]
