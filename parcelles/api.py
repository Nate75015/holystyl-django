"""API DRF parcelles & stades culturaux (parité `parcelles.*` tRPC).

Toutes les requêtes sont filtrées par l'exploitation courante (multi-tenant).
"""

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import CropStage, Parcelle, ParcelleCampagne
from .serializers import (
    CropStageSerializer,
    ParcelleCampagneSerializer,
    ParcelleSerializer,
)


def _current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class ParcelleViewSet(viewsets.ModelViewSet):
    serializer_class = ParcelleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        exploitation = _current_exploitation(self.request)
        if exploitation is None:
            return Parcelle.objects.none()
        return Parcelle.objects.filter(exploitation=exploitation)

    def perform_create(self, serializer):
        exploitation = _current_exploitation(self.request)
        if exploitation is None:
            raise ValidationError("Aucune exploitation : complétez d'abord l'onboarding.")
        serializer.save(exploitation=exploitation)


class ParcelleCampagneViewSet(viewsets.ModelViewSet):
    serializer_class = ParcelleCampagneSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        exploitation = _current_exploitation(self.request)
        qs = ParcelleCampagne.objects.filter(parcelle__exploitation=exploitation)
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs


class CropStageViewSet(viewsets.ModelViewSet):
    serializer_class = CropStageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        exploitation = _current_exploitation(self.request)
        qs = CropStage.objects.filter(parcelle_campagne__parcelle__exploitation=exploitation)
        campagne_id = self.request.query_params.get("campagne")
        if campagne_id:
            return qs.filter(parcelle_campagne_id=campagne_id)
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_campagne__parcelle_id=parcelle_id) if parcelle_id else qs
