from django.urls import path

from . import views

app_name = "elevage"

urlpatterns = [
    path("elevage/", views.elevage, name="elevage"),
    path("especes/nouvelle/", views.espece_create, name="espece_create"),
    path("especes/<int:pk>/modifier/", views.espece_edit, name="espece_edit"),
    path("especes/<int:pk>/supprimer/", views.espece_delete, name="espece_delete"),
    path("races/nouvelle/", views.race_create, name="race_create"),
    path("races/<int:pk>/modifier/", views.race_edit, name="race_edit"),
    path("races/<int:pk>/supprimer/", views.race_delete, name="race_delete"),
]
