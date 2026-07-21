from django.urls import path

from . import views

app_name = "irrigation"

urlpatterns = [
    path("irrigation/", views.irrigation, name="irrigation"),
    path("dti/", views.dti, name="dti"),
    path("dti/calculer/", views.dti_calculate, name="dti_calculate"),
    path("irrigation/zones/nouvelle/", views.zone_create, name="zone_create"),
    path("irrigation/programmes/nouveau/", views.program_create, name="program_create"),
    path("irrigation/stations/nouvelle/", views.station_create, name="station_create"),
    path("bassinage/", views.bassinage, name="bassinage"),
    path("bassinage/declencher/", views.bassinage_create, name="bassinage_create"),
    path("anti-gel/", views.antigel, name="antigel"),
    path("anti-gel/reglages/", views.antigel_settings, name="antigel_settings"),
]
