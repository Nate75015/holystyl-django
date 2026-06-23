"""API DRF de l'assistant IA (parité `ai.*` tRPC)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exploitations.models import Exploitation

from . import services
from .models import AiConversation, DailyReport


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


class AiChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        history = request.data.get("history", [])
        if not message:
            return Response({"error": "message vide"}, status=400)
        answer = services.chat(_exploitation(request), request.user, message, history)
        return Response({"response": answer})


class AiExecuteIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        history = request.data.get("history", [])
        if not message:
            return Response({"error": "message vide"}, status=400)
        result = services.execute_intent(_exploitation(request), request.user, message, history)
        return Response(result)


class AiConversationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AiConversation.objects.filter(exploitation=_exploitation(request)).order_by("created_at")[:100]
        return Response([
            {"role": c.role, "content": c.content, "createdAt": c.created_at.isoformat()} for c in qs
        ])


class AiGenerateReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        report = services.generate_daily_report(_exploitation(request))
        return Response({
            "id": report.id,
            "date": report.report_date.isoformat(),
            "dtiScore": report.dti_score,
            "summary": report.summary,
            "recommendations": report.recommendations,
        })


class AiReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DailyReport.objects.filter(exploitation=_exploitation(request))[:30]
        return Response([
            {"id": r.id, "date": r.report_date.isoformat(), "dtiScore": r.dti_score, "summary": r.summary}
            for r in qs
        ])
