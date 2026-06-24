from django.urls import path

from . import views

app_name = "meteo"

urlpatterns = [
    path("meteo/", views.meteo_index, name="index"),
    path("meteo/capturer/", views.meteo_capturer, name="capturer"),
    path("meteo/cron/capturer/", views.cron_capturer, name="cron_capturer"),
    path("meteo/villes/ajouter/", views.ville_add, name="ville_add"),
    path("meteo/villes/<int:pk>/supprimer/", views.ville_delete, name="ville_delete"),
    path("meteo/<slug:slug>/capture-auto/", views.capture_config, name="capture_config"),
    path("meteo/<slug:slug>/", views.meteo_detail, name="detail"),
]
