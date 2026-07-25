from django.urls import path

from . import views

app_name = "parcelles"

urlpatterns = [
    path("parcelles/", views.parcelle_list, name="list"),
    path("parcelles/cadastre/", views.parcelle_cadastre, name="cadastre"),
    path("parcelles/cadastre/enregistrer/", views.parcelle_cadastre_save, name="cadastre_save"),
    path("parcelles/nouvelle/", views.parcelle_create, name="create"),
    path("parcelles/<int:pk>/", views.parcelle_detail, name="detail"),
    path("parcelles/<int:pk>/modifier/", views.parcelle_edit, name="edit"),
    path("parcelles/<int:pk>/supprimer/", views.parcelle_delete, name="delete"),
    path("campagnes/", views.campagne_list, name="campagnes"),
    path("campagnes/nouvelle/", views.campagne_new, name="campagne_new"),
    path("parcelles/<int:parcelle_pk>/campagnes/nouvelle/", views.campagne_create, name="campagne_create"),
    path("campagnes/<int:pk>/modifier/", views.campagne_edit, name="campagne_edit"),
    path("campagnes/<int:pk>/supprimer/", views.campagne_delete, name="campagne_delete"),
]
