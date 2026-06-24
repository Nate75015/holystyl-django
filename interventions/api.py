"""API DRF interventions (`interventions.*`)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from exploitations.models import Exploitation

from .models import Intervention
from .serializers import InterventionSerializer


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class InterventionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InterventionSerializer

    def get_queryset(self):
        qs = Intervention.objects.filter(exploitation=current_exploitation(self.request))
        parcelle_id = self.request.query_params.get("parcelle")
        return qs.filter(parcelle_id=parcelle_id) if parcelle_id else qs

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request), user=self.request.user)
