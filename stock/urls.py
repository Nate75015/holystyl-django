from django.urls import path

from . import views

app_name = "stock"

urlpatterns = [
    path("stock/", views.articles, name="articles"),
    path("stock/articles/enregistrer/", views.article_save, name="article_save"),
    path("stock/articles/<int:pk>/supprimer/", views.article_delete, name="article_delete"),
    path("stock/recoltes/", views.recoltes, name="recoltes"),
    path("stock/recoltes/nouvelle/", views.recolte_create, name="recolte_create"),
    path("stock/mouvements/", views.mouvements, name="mouvements"),
    path("stock/mouvements/nouveau/", views.mouvement_create, name="mouvement_create"),
    path("stock/depots/", views.depots, name="depots"),
    path("stock/depots/enregistrer/", views.depot_save, name="depot_save"),
    path("stock/depots/<int:pk>/supprimer/", views.depot_delete, name="depot_delete"),
]
