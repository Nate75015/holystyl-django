"""API DRF opérations (parité `machines.*`, `interventions.*`, `entretiens.*`,
`affectations.*`, `catalogue.*`)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import AffectationEngin, CatalogueEngin, EntretienMateriel, Intervention, Machine, MachineLog
from .serializers import (
    AffectationEnginSerializer,
    CatalogueEnginSerializer,
    EntretienMaterielSerializer,
    InterventionSerializer,
    MachineLogSerializer,
    MachineSerializer,
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


class MachineViewSet(_TenantViewSet):
    model = Machine
    serializer_class = MachineSerializer


class MachineLogViewSet(_TenantViewSet):
    model = MachineLog
    serializer_class = MachineLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        machine_id = self.request.query_params.get("machine")
        return qs.filter(machine_id=machine_id) if machine_id else qs


class InterventionViewSet(_TenantViewSet):
    model = Intervention
    serializer_class = InterventionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request), user=self.request.user)


class EntretienMaterielViewSet(_TenantViewSet):
    model = EntretienMateriel
    serializer_class = EntretienMaterielSerializer


class AffectationEnginViewSet(_TenantViewSet):
    model = AffectationEngin
    serializer_class = AffectationEnginSerializer


class CatalogueEnginViewSet(viewsets.ReadOnlyModelViewSet):
    """Référentiel global (lecture seule)."""

    queryset = CatalogueEngin.objects.all()
    serializer_class = CatalogueEnginSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        type_filter = self.request.query_params.get("type")
        marque = self.request.query_params.get("marque")
        if type_filter:
            qs = qs.filter(type=type_filter)
        if marque:
            qs = qs.filter(marque__icontains=marque)
        return qs
