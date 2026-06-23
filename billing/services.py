"""Génération de codes d'activation et activation post-paiement (parité Stripe)."""

import secrets
import string

from django.core.mail import send_mail
from django.utils import timezone

from .models import ActivationCode

_ALPHABET = string.ascii_uppercase + string.digits


def generate_activation_code() -> str:
    """Code lisible HOLS-XXXX-XXXX, garanti unique."""
    def segment():
        return "".join(secrets.choice(_ALPHABET) for _ in range(4))

    while True:
        code = f"HOLS-{segment()}-{segment()}"
        if not ActivationCode.objects.filter(code=code).exists():
            return code


def create_activation_for_purchase(email: str, *, session_id="", customer_id="", subscription_id="") -> ActivationCode:
    """Crée un code d'activation après un paiement Stripe et envoie l'email."""
    code = ActivationCode.objects.create(
        code=generate_activation_code(),
        email=email,
        stripe_session_id=session_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    send_mail(
        "Votre accès Holystyl est prêt 🌱",
        f"Merci pour votre confiance !\n\nVotre code d'activation : {code.code}\n\n"
        f"Activez votre compte sur /activer en saisissant ce code.",
        None,
        [email],
        fail_silently=True,
    )
    return code


def activate_code(code_str: str, user, exploitation=None) -> ActivationCode | None:
    """Active un code pour un utilisateur. Renvoie le code activé ou None si invalide."""
    code = ActivationCode.objects.filter(code=code_str, status=ActivationCode.Status.PENDING).first()
    if code is None:
        return None
    if code.expires_at and code.expires_at < timezone.now():
        code.status = ActivationCode.Status.EXPIRED
        code.save(update_fields=["status"])
        return None
    code.status = ActivationCode.Status.USED
    code.used_at = timezone.now()
    code.used_by = user
    code.exploitation = exploitation
    code.save()
    return code
