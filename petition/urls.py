from django.urls import path

from . import views

app_name = "petition"

urlpatterns = [
    path("petitions/", views.liste, name="liste"),
    path("petitions/nouveau/", views.create, name="create"),
    path("petitions/reformuler/", views.reformuler, name="reformuler"),
    path("petitions/<int:pk>/", views.detail, name="detail"),
    path("petitions/<int:pk>/signer/", views.signer, name="signer"),
    path("petitions/<int:pk>/cloturer/", views.cloturer, name="cloturer"),
]
