"""Routage de l'API REST (DRF) — équivalent des procedures tRPC d'origine.

Conventions : /api/<ressource>/ . Élargi au fil des tranches.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from agronomie.api import CultureKcViewSet, SaisonViewSet, TypeSolViewSet
from exploitations.api import CurrentExploitationView, ExploitationKPIsView
from ia.api import (
    AiChatView,
    AiConversationsView,
    AiExecuteIntentView,
    AiGenerateReportView,
    AiReportListView,
)
from notifications.api import NotificationRuleViewSet, NotificationViewSet
from iot.api import IotAlertViewSet, IotDeviceViewSet, ThresholdViewSet
from iot.rest import IotCommandCallbackView, IotCommandPollView, IotIngestView
from irrigation.api import (
    BassinageEventViewSet,
    DtiCalculateView,
    DtiLatestView,
    IrrigationProgramViewSet,
    IrrigationSessionViewSet,
    IrrigationZoneViewSet,
    PumpingStationViewSet,
    WaterMeterViewSet,
    WaterQuotaViewSet,
)
from parcelles.api import CropStageViewSet, ParcelleViewSet

router = DefaultRouter()
# Tranche 1
router.register("parcelles", ParcelleViewSet, basename="parcelle")
router.register("crop-stages", CropStageViewSet, basename="cropstage")
router.register("cultures-kc", CultureKcViewSet, basename="culturekc")
router.register("types-sol", TypeSolViewSet, basename="typesol")
router.register("saisons", SaisonViewSet, basename="saison")
# Tranche 2 — IoT
router.register("devices", IotDeviceViewSet, basename="device")
router.register("alerts", IotAlertViewSet, basename="alert")
router.register("thresholds", ThresholdViewSet, basename="threshold")
# Tranche 2 — irrigation & hydrique
router.register("irrigation/zones", IrrigationZoneViewSet, basename="izone")
router.register("irrigation/programs", IrrigationProgramViewSet, basename="iprogram")
router.register("irrigation/sessions", IrrigationSessionViewSet, basename="isession")
router.register("irrigation/pumping", PumpingStationViewSet, basename="ipump")
router.register("irrigation/bassinage", BassinageEventViewSet, basename="ibassinage")
router.register("water/meters", WaterMeterViewSet, basename="wmeter")
router.register("water/quotas", WaterQuotaViewSet, basename="wquota")
# Tranche 3 — notifications
router.register("notifications", NotificationViewSet, basename="notification")
router.register("notification-rules", NotificationRuleViewSet, basename="notificationrule")

urlpatterns = [
    path("exploitation/", CurrentExploitationView.as_view(), name="api-exploitation"),
    path("exploitation/kpis/", ExploitationKPIsView.as_view(), name="api-exploitation-kpis"),
    # DTI
    path("dti/calculate/", DtiCalculateView.as_view(), name="api-dti-calculate"),
    path("dti/latest/", DtiLatestView.as_view(), name="api-dti-latest"),
    # IoT — gateways (auth par device-token, hors session)
    path("iot/ingest/", IotIngestView.as_view(), name="api-iot-ingest"),
    path("iot/command/poll/", IotCommandPollView.as_view(), name="api-iot-poll"),
    path("iot/command/callback/", IotCommandCallbackView.as_view(), name="api-iot-callback"),
    # Assistant IA
    path("ai/chat/", AiChatView.as_view(), name="api-ai-chat"),
    path("ai/execute-intent/", AiExecuteIntentView.as_view(), name="api-ai-intent"),
    path("ai/conversations/", AiConversationsView.as_view(), name="api-ai-conversations"),
    path("ai/report/", AiGenerateReportView.as_view(), name="api-ai-report"),
    path("ai/reports/", AiReportListView.as_view(), name="api-ai-reports"),
    path("", include(router.urls)),
]
