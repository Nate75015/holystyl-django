from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("parc-materiel/", views.parc_materiel, name="parc_materiel"),
]
