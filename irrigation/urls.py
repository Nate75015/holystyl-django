from django.urls import path

from . import views

app_name = "irrigation"

urlpatterns = [
    path("irrigation/", views.irrigation, name="irrigation"),
    path("irrigation/zones/nouvelle/", views.zone_create, name="zone_create"),
    path("irrigation/programmes/nouveau/", views.program_create, name="program_create"),
    path("irrigation/stations/nouvelle/", views.station_create, name="station_create"),
    path("bassinage/", views.bassinage, name="bassinage"),
]
