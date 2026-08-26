from django.urls import path

from . import views, vitrine

app_name = "vente"

urlpatterns = [
    # ── Producteur (espace exploitant) ──────────────────────────────
    path("vente/boutique/", views.boutique, name="boutique"),
    path("vente/produits/", views.produits, name="produits"),
    path("vente/produits/enregistrer/", views.produit_save, name="produit_save"),
    path("vente/produits/<int:pk>/publier/", views.produit_publier, name="produit_publier"),
    path("vente/produits/<int:pk>/retirer/", views.produit_retirer, name="produit_retirer"),
    path("vente/produits/<int:pk>/supprimer/", views.produit_delete, name="produit_delete"),
    path("vente/commandes/", views.commandes, name="commandes"),
    path("vente/commandes/<int:pk>/", views.commande_detail, name="commande_detail"),
    path("vente/commandes/<int:pk>/facturer/", views.commande_facturer, name="commande_facturer"),
    path("vente/commandes/<int:pk>/<slug:action>/", views.commande_transition, name="commande_transition"),
    path("mes-commandes/", views.mes_commandes, name="mes_commandes"),

    # ── Vitrine publique ────────────────────────────────────────────
    path("marche/", vitrine.marche, name="marche"),
    path("marche/<slug:categorie>/", vitrine.marche, name="marche_categorie"),
    path("ferme/<slug:slug>/", vitrine.boutique_publique, name="boutique_publique"),
    path("ferme/<slug:slug>/<slug:produit_slug>/", vitrine.produit_public, name="produit_public"),
    path("panier/", vitrine.panier, name="panier"),
    path("panier/ajouter/", vitrine.panier_ajouter, name="panier_ajouter"),
    path("panier/ligne/<int:produit_id>/", vitrine.panier_ligne, name="panier_ligne"),
    path("panier/valider/", vitrine.commander, name="commander"),
    path("commande/<uuid:jeton>/", vitrine.suivi, name="suivi"),
]
