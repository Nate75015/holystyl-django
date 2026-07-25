from django.urls import path

from . import views

app_name = "aquaculture"

urlpatterns = [
    path("aquaculture/", views.bassins, name="bassins"),
    path("aquaculture/nouvelle/", views.bassin_create, name="create"),
    path("aquaculture/<int:pk>/", views.bassin_detail, name="detail"),
    path("aquaculture/<int:pk>/modifier/", views.bassin_edit, name="edit"),
    path("aquaculture/<int:pk>/supprimer/", views.bassin_delete, name="delete"),
    path("aquaculture/<int:pk>/lots/nouveau/", views.lot_create, name="lot_create"),
    path("aquaculture/lots/<int:pk>/supprimer/", views.lot_delete, name="lot_delete"),
    # Référentiel espèces & souches
    path("aquaculture/especes/", views.especes, name="especes"),
    path("aquaculture/especes/nouvelle/", views.espece_create, name="espece_create"),
    path("aquaculture/especes/<int:pk>/modifier/", views.espece_edit, name="espece_edit"),
    path("aquaculture/especes/<int:pk>/supprimer/", views.espece_delete, name="espece_delete"),
    path("aquaculture/souches/nouvelle/", views.souche_create, name="souche_create"),
    path("aquaculture/souches/<int:pk>/modifier/", views.souche_edit, name="souche_edit"),
    path("aquaculture/souches/<int:pk>/supprimer/", views.souche_delete, name="souche_delete"),
]
