"""API DRF irrigation & hydrique (parité `irrigation.*`, `water.*`, `dti.*`)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exploitations.models import Exploitation

from .models import (
    BassinageEvent,
    DtiScore,
    IrrigationProgram,
    IrrigationSession,
    IrrigationZone,
    PumpingStation,
    WaterMeter,
    WaterQuota,
)
from .serializers import (
    BassinageEventSerializer,
    DtiScoreSerializer,
    IrrigationProgramSerializer,
    IrrigationSessionSerializer,
    IrrigationZoneSerializer,
    PumpingStationSerializer,
    WaterMeterSerializer,
    WaterQuotaSerializer,
)
from .services import calculate_dti_score


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class _TenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    model = None

    def get_queryset(self):
        return self.model.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))


class IrrigationZoneViewSet(_TenantViewSet):
    model = IrrigationZone
    serializer_class = IrrigationZoneSerializer


class IrrigationProgramViewSet(_TenantViewSet):
    model = IrrigationProgram
    serializer_class = IrrigationProgramSerializer


class IrrigationSessionViewSet(_TenantViewSet):
    model = IrrigationSession
    serializer_class = IrrigationSessionSerializer


class PumpingStationViewSet(_TenantViewSet):
    model = PumpingStation
    serializer_class = PumpingStationSerializer


class BassinageEventViewSet(_TenantViewSet):
    model = BassinageEvent
    serializer_class = BassinageEventSerializer


class WaterMeterViewSet(_TenantViewSet):
    model = WaterMeter
    serializer_class = WaterMeterSerializer


class WaterQuotaViewSet(_TenantViewSet):
    model = WaterQuota
    serializer_class = WaterQuotaSerializer


class DtiCalculateView(APIView):
    """Calcule (et persiste) un score DTI à partir de kWh/m³ et de l'uniformité."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        exploitation = current_exploitation(request)
        kwh = float(request.data.get("kwhPerM3", 0))
        uniformity = float(request.data.get("uniformity", 90))
        result = calculate_dti_score(kwh, uniformity)
        score = DtiScore.objects.create(
            exploitation=exploitation,
            parcelle_id=request.data.get("parcelleId"),
            score=result.score,
            score_numeric=result.numeric,
            kwh_per_m3=kwh,
            uniformity_coeff=uniformity,
            recommendations=result.recommendations,
        )
        return Response(DtiScoreSerializer(score).data)


class DtiLatestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        score = DtiScore.objects.filter(exploitation=current_exploitation(request)).first()
        return Response(DtiScoreSerializer(score).data if score else None)
