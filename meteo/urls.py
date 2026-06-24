from django.urls import path

from . import views

app_name = "meteo"

urlpatterns = [
    path("meteo/", views.meteo, name="meteo"),
]
