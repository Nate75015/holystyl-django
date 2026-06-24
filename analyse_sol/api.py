"""API DRF analyses de sol (`analysesSol.*`)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import AnalyseSol
from .serializers import AnalyseSolSerializer


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class AnalyseSolViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnalyseSolSerializer

    def get_queryset(self):
        qs = AnalyseSol.objects.filter(exploitation=current_exploitation(self.request))
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request))
