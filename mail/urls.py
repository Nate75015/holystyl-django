from django.urls import path

from . import views

app_name = "mail"

urlpatterns = [
    path("mail/", views.outbox, name="outbox"),
    path("mail/nouveau/", views.compose, name="compose"),
    path("mail/<int:pk>/", views.detail, name="detail"),
]
