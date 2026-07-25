from django.urls import path

from . import views

app_name = "ia"

urlpatterns = [
    path("assistant/", views.assistant, name="assistant"),
    path("assistant/stream/", views.stream, name="stream"),
    path("assistant/reformuler/", views.reformuler, name="reformuler"),
]
