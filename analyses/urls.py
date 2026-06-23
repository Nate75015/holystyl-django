from django.urls import path

from . import views

app_name = "analyses"

urlpatterns = [
    path("laboratoire/", views.laboratoire, name="laboratoire"),
    path("analyses-sol/", views.analyses_sol, name="analyses_sol"),
]
