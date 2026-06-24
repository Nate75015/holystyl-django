from django.urls import path

from . import views

app_name = "agronomie"

urlpatterns = [
    path("cultures/", views.cultures, name="cultures"),
    path("cultures/nouvelle/", views.culture_create, name="culture_create"),
    path("cultures/<int:pk>/supprimer/", views.culture_delete, name="culture_delete"),
    path("types-sol/", views.types_sol, name="types_sol"),
    path("types-sol/nouveau/", views.type_sol_create, name="type_sol_create"),
    path("types-sol/<int:pk>/supprimer/", views.type_sol_delete, name="type_sol_delete"),
    path("saisons/", views.saisons, name="saisons"),
    path("fertigation/", views.fertigation, name="fertigation"),
    path("fertigation/apport/", views.fertigation_create, name="fertigation_create"),
]
