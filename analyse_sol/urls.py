from django.urls import path

from . import views

app_name = "analyse_sol"

urlpatterns = [
    path("analyses-sol/", views.analyses_sol, name="analyses_sol"),
    path("analyses-sol/importer/", views.analyse_sol_create, name="create"),
    path("analyses-sol/<int:pk>/", views.analyse_sol_detail, name="detail"),
    path("analyses-sol/<int:pk>/modifier/", views.analyse_sol_edit, name="edit"),
    path("analyses-sol/<int:pk>/supprimer/", views.analyse_sol_delete, name="delete"),
    path("analyses-sol/demander/", views.demande_create, name="demande_create"),
]
