from django.urls import path

from . import views

app_name = "parcelles"

urlpatterns = [
    path("parcelles/", views.parcelle_list, name="list"),
    path("parcelles/nouvelle/", views.parcelle_create, name="create"),
    path("parcelles/<int:pk>/", views.parcelle_detail, name="detail"),
    path("parcelles/<int:pk>/modifier/", views.parcelle_edit, name="edit"),
    path("parcelles/<int:pk>/supprimer/", views.parcelle_delete, name="delete"),
]
