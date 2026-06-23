from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.center, name="center"),
]
