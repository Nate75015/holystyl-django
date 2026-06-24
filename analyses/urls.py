from django.urls import path

from . import views

app_name = "analyses"

urlpatterns = [
    path("laboratoire/", views.laboratoire, name="laboratoire"),
]
