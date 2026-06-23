"""API DRF agronomie : référentiels Kc / sols (lecture) et saisons (CRUD)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import CultureKc, Saison, TypeSol
from .serializers import CultureKcSerializer, SaisonSerializer, TypeSolSerializer


class CultureKcViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CultureKc.objects.all()
    serializer_class = CultureKcSerializer
    permission_classes = [IsAuthenticated]


class TypeSolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TypeSol.objects.all()
    serializer_class = TypeSolSerializer
    permission_classes = [IsAuthenticated]


class SaisonViewSet(viewsets.ModelViewSet):
    serializer_class = SaisonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        exploitation = Exploitation.objects.filter(owner=self.request.user).first()
        return Saison.objects.filter(exploitation=exploitation) if exploitation else Saison.objects.none()

    def perform_create(self, serializer):
        exploitation = Exploitation.objects.filter(owner=self.request.user).first()
        serializer.save(exploitation=exploitation)
