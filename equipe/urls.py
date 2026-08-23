from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("equipe/", views.equipe, name="equipe"),
    path("equipe/<int:pk>/modifier/", views.membre_edit, name="membre_edit"),
    path("equipe/<int:pk>/supprimer/", views.membre_delete, name="membre_delete"),
    path("equipe/<int:pk>/inviter/", views.membre_inviter, name="membre_inviter"),
    path("equipe/invitation/<str:token>/", views.invitation, name="invitation"),
    path("taches/", views.taches, name="taches"),
    path("taches/<int:pk>/modifier/", views.taches_edit, name="taches_edit"),
    path("taches/<int:pk>/supprimer/", views.taches_delete, name="taches_delete"),
    path("contrats-travail/", views.contrats, name="contrats"),
    path("paie/", views.paie, name="paie"),
    path("localisation/<str:token>/", views.location_share, name="location_share"),
]
