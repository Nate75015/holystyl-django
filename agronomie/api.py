"""API DRF agronomie : référentiels Kc / sols (lecture) et fertigation (CRUD)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import CultureKc, Fertigation, TypeSol
from .serializers import (
    CultureKcSerializer,
    FertigationSerializer,
    TypeSolSerializer,
)


class CultureKcViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CultureKc.objects.all()
    serializer_class = CultureKcSerializer
    permission_classes = [IsAuthenticated]


class TypeSolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TypeSol.objects.all()
    serializer_class = TypeSolSerializer
    permission_classes = [IsAuthenticated]


class FertigationViewSet(viewsets.ModelViewSet):
    serializer_class = FertigationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        exploitation = Exploitation.objects.filter(owner=self.request.user).first()
        qs = Fertigation.objects.filter(exploitation=exploitation) if exploitation else Fertigation.objects.none()
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs

    def perform_create(self, serializer):
        serializer.save(exploitation=Exploitation.objects.filter(owner=self.request.user).first())
