from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("planning/", views.planning, name="planning"),
    path("planning/taches/nouvelle/", views.task_create, name="task_create"),
    path("planning/taches/<int:pk>/modifier/", views.task_edit, name="task_edit"),
    path("planning/taches/<int:pk>/supprimer/", views.task_delete, name="task_delete"),
    path("planning/reservations/nouvelle/", views.reservation_create, name="reservation_create"),
    path("planning/reservations/<int:pk>/modifier/", views.reservation_edit, name="reservation_edit"),
    path("planning/reservations/<int:pk>/supprimer/", views.reservation_delete, name="reservation_delete"),
    path("bon-intervention/<int:task_id>/", views.bon_intervention, name="bon_intervention"),
]
