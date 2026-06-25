from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("lead/", views.lead_capture, name="lead_capture"),
    path("alex/", views.alex, name="alex"),
]
