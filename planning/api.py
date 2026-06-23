"""API DRF planning (parité `planning.*`) + bons d'intervention & matériel."""

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exploitations.models import Exploitation

from .models import (
    EquipmentCatalog,
    InterventionReport,
    PlanningAbsence,
    PlanningTask,
    PlanningTimeLog,
)
from .serializers import (
    EquipmentCatalogSerializer,
    InterventionReportSerializer,
    PlanningAbsenceSerializer,
    PlanningTaskSerializer,
    PlanningTimeLogSerializer,
)


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class _TenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    model = None

    def get_queryset(self):
        return self.model.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))


class PlanningTaskViewSet(_TenantViewSet):
    model = PlanningTask
    serializer_class = PlanningTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("technicienId"):
            qs = qs.filter(technicien_id=params["technicienId"])
        if params.get("statut"):
            qs = qs.filter(statut=params["statut"])
        if params.get("type"):
            qs = qs.filter(type=params["type"])
        if params.get("backlog") == "true":
            qs = qs.filter(is_backlog=True)
        return qs

    @action(detail=True, methods=["post"], url_path="log-time")
    def log_time(self, request, pk=None):
        task = self.get_object()
        log = PlanningTimeLog.objects.create(
            task=task,
            exploitation=task.exploitation,
            action=request.data.get("action"),
            timestamp=timezone.now(),
            technicien_id=request.data.get("technicienId"),
        )
        # Synchronise le statut de la tâche selon l'action
        mapping = {"start": "en_cours", "pause": "en_pause", "resume": "en_cours", "complete": "termine"}
        if log.action in mapping:
            task.statut = mapping[log.action]
            if log.action == "complete":
                task.completed_at = timezone.now()
            task.save(update_fields=["statut", "completed_at"])
        return Response(PlanningTimeLogSerializer(log).data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            "total": qs.count(),
            "planifie": qs.filter(statut="planifie").count(),
            "en_cours": qs.filter(statut="en_cours").count(),
            "termine": qs.filter(statut="termine").count(),
            "backlog": qs.filter(is_backlog=True).count(),
        })


class PlanningAbsenceViewSet(_TenantViewSet):
    model = PlanningAbsence
    serializer_class = PlanningAbsenceSerializer


class EquipmentCatalogViewSet(_TenantViewSet):
    model = EquipmentCatalog
    serializer_class = EquipmentCatalogSerializer


class InterventionReportViewSet(_TenantViewSet):
    model = InterventionReport
    serializer_class = InterventionReportSerializer

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        report = self.get_object()
        report.statut = InterventionReport.Statut.VALIDE
        report.save(update_fields=["statut"])
        return Response(InterventionReportSerializer(report).data)
