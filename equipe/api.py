"""API DRF équipe & tâches (parité `equipe.*`, `taches.*`)."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exploitations.models import Exploitation

from .models import Task, TeamMember
from .serializers import TaskSerializer, TeamMemberSerializer
from .services import generate_location_link, notify_task_assignment


def current_exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class TeamMemberViewSet(viewsets.ModelViewSet):
    serializer_class = TeamMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TeamMember.objects.filter(exploitation=current_exploitation(self.request))

    def perform_create(self, serializer):
        serializer.save(exploitation=current_exploitation(self.request), managed_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="location-link")
    def location_link(self, request, pk=None):
        member = self.get_object()
        token = generate_location_link(member)
        return Response({"token": token, "url": request.build_absolute_uri(f"/localisation/{token}/")})

    @action(detail=True, methods=["post"], url_path="position")
    def position(self, request, pk=None):
        member = self.get_object()
        member.lat = request.data.get("lat")
        member.lng = request.data.get("lng")
        from django.utils import timezone

        member.last_seen_at = timezone.now()
        member.is_online = True
        member.save(update_fields=["lat", "lng", "last_seen_at", "is_online"])
        return Response({"ok": True})


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Task.objects.filter(exploitation=current_exploitation(self.request))
        status_filter = self.request.query_params.get("status")
        assigned = self.request.query_params.get("assignedTo")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if assigned:
            qs = qs.filter(assigned_to_id=assigned)
        return qs

    def perform_create(self, serializer):
        task = serializer.save(exploitation=current_exploitation(self.request), created_by=self.request.user)
        if task.assigned_to_id:
            sent = notify_task_assignment(task)
            if sent:
                task.sms_sent_24h = False  # marqueur d'envoi initial laissé aux rappels
