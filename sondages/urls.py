from django.urls import path

from . import views

app_name = "sondages"

urlpatterns = [
    path("sondages/", views.liste, name="liste"),
    path("sondages/nouveau/", views.create, name="create"),
    path("sondages/<int:pk>/", views.detail, name="detail"),
    path("sondages/<int:pk>/voter/", views.vote, name="vote"),
    path("sondages/<int:pk>/cloturer/", views.cloturer, name="cloturer"),
]
