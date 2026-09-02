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
    path("contrats-travail/modeles/importer/", views.modeles_importer, name="modeles_importer"),
    path("contrats-travail/modeles/enregistrer/", views.modele_save, name="modele_create"),
    path("contrats-travail/modeles/<int:pk>/enregistrer/", views.modele_save, name="modele_edit"),
    path("contrats-travail/modeles/<int:pk>/supprimer/", views.modele_delete, name="modele_delete"),
    path("contrats-travail/etablir/", views.contrat_create, name="contrat_create"),
    path("contrats-travail/<int:pk>/enregistrer/", views.contrat_edit, name="contrat_edit"),
    path("contrats-travail/<int:pk>/supprimer/", views.contrat_delete, name="contrat_delete"),
    path("contrats-travail/<int:pk>/pdf/", views.contrat_pdf, name="contrat_pdf"),
    path("paie/", views.paie, name="paie"),
    path("localisation/<str:token>/", views.location_share, name="location_share"),
]
