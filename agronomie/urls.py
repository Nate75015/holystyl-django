from django.urls import path

from . import views

app_name = "agronomie"

urlpatterns = [
    path("cultures-kc/", views.cultures_kc, name="cultures_kc"),
    path("types-sol/", views.types_sol, name="types_sol"),
    path("saisons/", views.saisons, name="saisons"),
]
