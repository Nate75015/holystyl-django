"""API DRF administration : configuration SMTP (parité `admin.*`)."""

from django.core.mail import get_connection, send_mail
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exploitations.models import Exploitation

from .models import SmtpConfig


class SmtpConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmtpConfig
        exclude = ["exploitation"]
        read_only_fields = ["id", "created_at", "updated_at", "last_tested_at", "last_test_status", "last_test_error"]
        extra_kwargs = {"password": {"write_only": True}}


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _build_connection(cfg: SmtpConfig):
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=cfg.host, port=cfg.port, username=cfg.user, password=cfg.password,
        use_tls=not cfg.secure, use_ssl=cfg.secure,
    )


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def smtp_config(request):
    exploitation = _exploitation(request)
    cfg = SmtpConfig.objects.filter(exploitation=exploitation).first()
    if request.method == "GET":
        return Response(SmtpConfigSerializer(cfg).data if cfg else None)

    serializer = SmtpConfigSerializer(cfg, data=request.data, partial=cfg is not None)
    serializer.is_valid(raise_exception=True)
    serializer.save(exploitation=exploitation)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def smtp_test(request):
    cfg = SmtpConfig.objects.filter(exploitation=_exploitation(request)).first()
    if cfg is None:
        return Response({"error": "Aucune configuration SMTP."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        conn = _build_connection(cfg)
        conn.open()
        conn.close()
        cfg.last_test_status, cfg.last_test_error = SmtpConfig.TestStatus.OK, ""
    except Exception as exc:
        cfg.last_test_status, cfg.last_test_error = SmtpConfig.TestStatus.ERROR, str(exc)
    cfg.last_tested_at = timezone.now()
    cfg.save(update_fields=["last_tested_at", "last_test_status", "last_test_error"])
    return Response({"status": cfg.last_test_status, "error": cfg.last_test_error})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def smtp_send_test(request):
    cfg = SmtpConfig.objects.filter(exploitation=_exploitation(request)).first()
    to = request.data.get("to")
    if not to:
        return Response({"error": "Destinataire requis."}, status=status.HTTP_400_BAD_REQUEST)
    connection = _build_connection(cfg) if cfg else None
    sent = send_mail(
        "Test email Holystyl",
        "Ceci est un email de test depuis Holystyl. Votre configuration SMTP fonctionne !",
        cfg.from_email if cfg else None,
        [to],
        connection=connection,
        fail_silently=True,
    )
    return Response({"sent": bool(sent)})
