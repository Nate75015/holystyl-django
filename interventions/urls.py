from django.urls import path

from . import views

app_name = "interventions"

urlpatterns = [
    path("interventions/", views.interventions, name="interventions"),
    path("interventions/nouvelle/", views.intervention_create, name="intervention_create"),
]
