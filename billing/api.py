"""API DRF billing (parité `activation.verify/activate`, `listSubscriptions`)."""

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exploitations.models import Exploitation

from .models import ActivationCode, Subscription
from .services import activate_code


class ActivationVerifyView(APIView):
    """Vérifie qu'un code est valide (public)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.query_params.get("code", "")
        exists = ActivationCode.objects.filter(code=code, status=ActivationCode.Status.PENDING).exists()
        return Response({"valid": exists})


class ActivationActivateView(APIView):
    """Active un code pour l'utilisateur connecté."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        code_str = request.data.get("code", "")
        exploitation = Exploitation.objects.filter(owner=request.user).first()
        code = activate_code(code_str, request.user, exploitation)
        if code is None:
            return Response({"success": False, "message": "Code invalide ou déjà utilisé."}, status=400)
        return Response({"success": True, "message": "Votre accès Holystyl est maintenant activé !"})


class SubscriptionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        exploitation = Exploitation.objects.filter(owner=request.user).first()
        sub = getattr(exploitation, "subscription", None) if exploitation else None
        if sub is None:
            return Response(None)
        return Response({
            "status": sub.status,
            "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancelAtPeriodEnd": sub.cancel_at_period_end,
        })
