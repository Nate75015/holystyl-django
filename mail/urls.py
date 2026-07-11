from django.urls import path

from . import views

app_name = "mail"

urlpatterns = [
    # Point d'entrée : Gmail si connecté, sinon écran de connexion
    path("mail/", views.outbox, name="outbox"),

    # Connexion OAuth Gmail
    path("mail/oauth/connect/", views.gmail_connect, name="gmail_connect"),
    path("mail/oauth/callback/", views.gmail_callback, name="gmail_callback"),
    path("mail/oauth/disconnect/", views.gmail_disconnect, name="gmail_disconnect"),

    # Boîte de réception Gmail (dossiers/libellés + lecture)
    path("mail/f/<str:folder>/", views.folder, name="folder"),
    path("mail/g/<str:mid>/", views.gmail_message, name="gmail_message"),

    # Composition + envoi via le compte Gmail connecté
    path("mail/nouveau/", views.compose, name="compose"),
]
