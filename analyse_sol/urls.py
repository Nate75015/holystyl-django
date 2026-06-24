from django.urls import path

from . import views

app_name = "analyse_sol"

urlpatterns = [
    path("analyses-sol/", views.analyses_sol, name="analyses_sol"),
]
