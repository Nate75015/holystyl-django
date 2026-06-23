"""Routage de l'API REST (DRF) — équivalent des procedures tRPC d'origine.

Conventions : /api/<ressource>/ . Élargi au fil des tranches.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from agronomie.api import CultureKcViewSet, SaisonViewSet, TypeSolViewSet
from exploitations.api import CurrentExploitationView, ExploitationKPIsView
from parcelles.api import CropStageViewSet, ParcelleViewSet

router = DefaultRouter()
router.register("parcelles", ParcelleViewSet, basename="parcelle")
router.register("crop-stages", CropStageViewSet, basename="cropstage")
router.register("cultures-kc", CultureKcViewSet, basename="culturekc")
router.register("types-sol", TypeSolViewSet, basename="typesol")
router.register("saisons", SaisonViewSet, basename="saison")

urlpatterns = [
    path("exploitation/", CurrentExploitationView.as_view(), name="api-exploitation"),
    path("exploitation/kpis/", ExploitationKPIsView.as_view(), name="api-exploitation-kpis"),
    path("", include(router.urls)),
]
