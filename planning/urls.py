from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("planning/", views.planning, name="planning"),
    path("bon-intervention/<int:task_id>/", views.bon_intervention, name="bon_intervention"),
]
