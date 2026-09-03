"""Routage de l'API REST (DRF) — équivalent des procedures tRPC d'origine.

Conventions : /api/<ressource>/ . Élargi au fil des tranches.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from administration.api import smtp_config, smtp_send_test, smtp_test
from agronomie.api import CultureKcViewSet, FertigationViewSet, TypeSolViewSet
from analyses.api import AnalysisResultViewSet, BiodiversiteFicheViewSet
from analyse_sol.api import AnalyseSolViewSet
from equipe.api import TaskViewSet, TeamMemberViewSet
from finances.api import (
    BilanView,
    ChargeViewSet,
    FactureClientViewSet,
    FactureViewSet,
    RecolteViewSet,
    RevenuViewSet,
)
from operations.api import (
    AffectationEnginViewSet,
    CatalogueEnginViewSet,
    EntretienMaterielViewSet,
    MachineLogViewSet,
    MachineViewSet,
)
from interventions.api import InterventionViewSet
from exploitations.api import CurrentExploitationView, ExploitationKPIsView
from planning.api import (
    EquipmentCatalogViewSet,
    InterventionReportViewSet,
    PlanningAbsenceViewSet,
    PlanningTaskViewSet,
)
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
from parcelles.api import (
    CropStageViewSet,
    ParcelleCampagneViewSet,
    ParcelleViewSet,
)

router = DefaultRouter()
# Tranche 1
router.register("parcelles", ParcelleViewSet, basename="parcelle")
router.register("parcelle-campagnes", ParcelleCampagneViewSet, basename="parcellecampagne")
router.register("crop-stages", CropStageViewSet, basename="cropstage")
router.register("cultures-kc", CultureKcViewSet, basename="culturekc")
router.register("types-sol", TypeSolViewSet, basename="typesol")
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
# Tranche 4 — équipe & planning
router.register("team", TeamMemberViewSet, basename="teammember")
router.register("tasks", TaskViewSet, basename="task")
router.register("planning/tasks", PlanningTaskViewSet, basename="planningtask")
router.register("planning/absences", PlanningAbsenceViewSet, basename="absence")
router.register("planning/equipment", EquipmentCatalogViewSet, basename="equipment")
router.register("planning/reports", InterventionReportViewSet, basename="report")
# Tranche 5 — opérations & analyses
router.register("machines", MachineViewSet, basename="machine")
router.register("machine-logs", MachineLogViewSet, basename="machinelog")
router.register("interventions", InterventionViewSet, basename="intervention")
router.register("entretiens", EntretienMaterielViewSet, basename="entretien")
router.register("affectations", AffectationEnginViewSet, basename="affectation")
router.register("catalogue-engins", CatalogueEnginViewSet, basename="catalogueengin")
router.register("fertigations", FertigationViewSet, basename="fertigation")
router.register("analyses/lab", AnalysisResultViewSet, basename="labresult")
router.register("analyses/sol", AnalyseSolViewSet, basename="analysesol")
router.register("analyses/biodiversite", BiodiversiteFicheViewSet, basename="biodiversite")
# Tranche 6 — finances
router.register("charges", ChargeViewSet, basename="charge")
router.register("revenus", RevenuViewSet, basename="revenu")
router.register("recoltes", RecolteViewSet, basename="recolte")
router.register("facture-clients", FactureClientViewSet, basename="factureclient")
router.register("factures", FactureViewSet, basename="facture")

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
    # Agent IA
    path("ai/chat/", AiChatView.as_view(), name="api-ai-chat"),
    path("ai/execute-intent/", AiExecuteIntentView.as_view(), name="api-ai-intent"),
    path("ai/conversations/", AiConversationsView.as_view(), name="api-ai-conversations"),
    path("ai/report/", AiGenerateReportView.as_view(), name="api-ai-report"),
    path("ai/reports/", AiReportListView.as_view(), name="api-ai-reports"),
    # Bilan ROI
    path("bilan/", BilanView.as_view(), name="api-bilan"),
    # Administration SMTP
    path("admin/smtp/", smtp_config, name="api-smtp-config"),
    path("admin/smtp/test/", smtp_test, name="api-smtp-test"),
    path("admin/smtp/send-test/", smtp_send_test, name="api-smtp-send-test"),
    path("", include(router.urls)),
]
