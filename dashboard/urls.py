"""Routes des tableaux de bord (un par espace).

`/pulse/` n'est pas déclaré ici : il reste porté par `core:dashboard`, qui
pointe sur l'aiguillage `index` et redirige vers l'espace courant.
"""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("tableau-de-bord/", views.exploitant, name="exploitant"),
    path("mon-espace/", views.employe, name="employe"),
    path("espace-bailleur/", views.bailleur, name="bailleur"),
    path("espace/basculer/", views.basculer, name="basculer"),
]
