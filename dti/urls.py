from django.urls import path

from . import views

app_name = "dti"

urlpatterns = [
    path("dti/receptions/", views.liste, name="liste"),
    path("dti/receptions/<int:pk>/", views.detail, name="detail"),
    path("dti/receptions/<int:pk>/rattacher/", views.rattachement, name="rattachement"),
]
