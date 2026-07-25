from django.urls import path

from . import views

app_name = "client"

urlpatterns = [
    path("clients/", views.clients, name="clients"),
    path("clients/nouveau/", views.client_create, name="create"),
    path("clients/<int:pk>/", views.client_detail, name="detail"),
    path("clients/<int:pk>/modifier/", views.client_edit, name="edit"),
    path("clients/<int:pk>/supprimer/", views.client_delete, name="delete"),
]
