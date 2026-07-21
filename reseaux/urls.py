from django.urls import path

from . import views

app_name = "reseaux"

urlpatterns = [
    path("reseaux/", views.reseaux, name="reseaux"),
    path("reseaux/demander/<int:user_id>/", views.demander, name="demander"),
    path("reseaux/<int:pk>/accepter/", views.accepter, name="accepter"),
    path("reseaux/<int:pk>/refuser/", views.refuser, name="refuser"),
    path("reseaux/<int:pk>/retirer/", views.retirer, name="retirer"),
]
