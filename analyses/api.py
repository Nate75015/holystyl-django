"""API DRF analyses (parité `lab.*`, `analysesSol.*`, `biodiversite.*`)."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exploitations.models import Exploitation

from .models import AnalyseSol, AnalysisResult, BiodiversiteFiche
from .serializers import AnalyseSolSerializer, AnalysisResultSerializer, BiodiversiteFicheSerializer
from .services import apply_extraction


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class _TenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    model = None

    def get_queryset(self):
        return self.model.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))


class AnalysisResultViewSet(_TenantViewSet):
    model = AnalysisResult
    serializer_class = AnalysisResultSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        type_filter = self.request.query_params.get("type")
        return qs.filter(analysis_type=type_filter) if type_filter else qs

    @action(detail=True, methods=["post"], url_path="extract")
    def extract(self, request, pk=None):
        """Lance l'extraction IA à partir du texte OCR fourni ou déjà stocké."""
        report = self.get_object()
        raw = request.data.get("ocrRawText")
        if raw:
            report.ocr_raw_text = raw
            report.save(update_fields=["ocr_raw_text"])
        applied = apply_extraction(report)
        return Response({"applied": applied, "report": AnalysisResultSerializer(report).data})


class AnalyseSolViewSet(_TenantViewSet):
    model = AnalyseSol
    serializer_class = AnalyseSolSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs


class BiodiversiteFicheViewSet(_TenantViewSet):
    model = BiodiversiteFiche
    serializer_class = BiodiversiteFicheSerializer
