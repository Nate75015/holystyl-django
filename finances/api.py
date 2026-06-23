"""API DRF finances (parité `charges.*`, `revenus.*`, `recoltes.*`, `facturation.*`, `bilan.*`)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exploitations.models import Exploitation

from .models import Charge, Facture, FactureClient, Recolte, Revenu
from .serializers import (
    ChargeSerializer,
    FactureClientSerializer,
    FactureSerializer,
    RecolteSerializer,
    RevenuSerializer,
)
from .services import compute_bilan


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class _TenantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    model = None

    def get_queryset(self):
        return self.model.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))


class ChargeViewSet(_TenantViewSet):
    model = Charge
    serializer_class = ChargeSerializer


class RevenuViewSet(_TenantViewSet):
    model = Revenu
    serializer_class = RevenuSerializer


class RecolteViewSet(_TenantViewSet):
    model = Recolte
    serializer_class = RecolteSerializer


class FactureClientViewSet(_TenantViewSet):
    model = FactureClient
    serializer_class = FactureClientSerializer


class FactureViewSet(_TenantViewSet):
    model = Facture
    serializer_class = FactureSerializer

    def perform_create(self, serializer):
        # Calcule TVA / TTC à partir du HT
        ht = float(serializer.validated_data.get("montant_ht", 0) or 0)
        taux = float(serializer.validated_data.get("taux_tva", 20) or 0)
        tva = round(ht * taux / 100, 2)
        serializer.save(
            exploitation=current_exploitation(self.request),
            montant_tva=tva,
            montant_ttc=round(ht + tva, 2),
        )


class BilanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from dataclasses import asdict

        year = request.query_params.get("year")
        year = int(year) if year and year.isdigit() else None
        return Response(asdict(compute_bilan(current_exploitation(request), year)))
