from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("nos-terroirs/", views.terroirs, name="terroirs"),
    path("lead/", views.lead_capture, name="lead_capture"),
    path("alex/", views.alex, name="alex"),
]
