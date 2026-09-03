from django.urls import path

from . import views

app_name = "identite"

# Les routes nommées d'abord : `<slug:type_piece>` avalerait « ajouter ».
urlpatterns = [
    path("identite/", views.pieces, name="pieces"),
    path("identite/ajouter/", views.piece_ajouter, name="piece_ajouter"),
    path("identite/scanner/", views.piece_scanner, name="piece_scanner"),
    path("identite/signature/definir/", views.signature_definir, name="signature_definir"),
    path("identite/signature/<int:pk>/activer/", views.signature_activer, name="signature_activer"),
    path("identite/<int:pk>/modifier/", views.piece_modifier, name="piece_modifier"),
    path("identite/<int:pk>/supprimer/", views.piece_supprimer, name="piece_supprimer"),
    path("identite/<slug:type_piece>/", views.pieces, name="pieces_type"),
]
