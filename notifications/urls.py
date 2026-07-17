from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.center, name="center"),
    path("notifications/regles/reformuler/", views.rule_reformulate, name="rule_reformulate"),
    path("notifications/regles/<int:pk>/modifier/", views.rule_edit, name="rule_edit"),
    path("notifications/regles/<int:pk>/basculer/", views.rule_toggle, name="rule_toggle"),
    path("notifications/regles/<int:pk>/supprimer/", views.rule_delete, name="rule_delete"),
]
