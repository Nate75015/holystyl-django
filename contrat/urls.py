from django.urls import path

from . import views

app_name = "contrat"

urlpatterns = [
    path("contrats/", views.contrats, name="contrats"),
    path("contrats/nouveau/", views.contrat_create, name="create"),
    path("contrats/<int:pk>/supprimer/", views.contrat_delete, name="delete"),
    path("baux/", views.baux, name="baux"),
    path("baux/nouveau/", views.bail_create, name="bail_create"),
    path("baux/<int:pk>/supprimer/", views.bail_delete, name="bail_delete"),
    path("actes-notaries/", views.actes_notaries, name="actes"),
    path("actes-notaries/nouveau/", views.acte_create, name="acte_create"),
    path("actes-notaries/<int:pk>/supprimer/", views.acte_delete, name="acte_delete"),
    path("assurances/", views.assurances, name="assurances"),
    path("assurances/nouvelle/", views.assurance_create, name="assurance_create"),
    path("assurances/<int:pk>/enregistrer/", views.assurance_create, name="assurance_edit"),
    path("assurances/<int:pk>/supprimer/", views.assurance_delete, name="assurance_delete"),
    path("assurances/scanner/", views.assurance_scanner, name="assurance_scanner"),
    path("assurances/<int:pk>/document/", views.assurance_document, name="assurance_document"),
    path("assurances/document/<int:pk>/supprimer/", views.assurance_document_delete,
         name="assurance_document_delete"),
    path("assurances/rendez-vous/", views.rendez_vous_create, name="rendez_vous_create"),
    path("msa/", views.msa, name="msa"),
    path("msa/nouvelle/", views.msa_create, name="msa_create"),
    path("msa/<int:pk>/supprimer/", views.msa_delete, name="msa_delete"),
]
