"""Envoi SMS via Twilio (équivalent server/sms.ts).

Repli propre : si les identifiants Twilio sont absents, le message est
journalisé (mode stub) plutôt qu'envoyé — aucune erreur, aucune donnée inventée.
"""

import logging

from django.conf import settings

logger = logging.getLogger("holystyl.sms")


def is_configured() -> bool:
    return bool(
        getattr(settings, "TWILIO_ACCOUNT_SID", "")
        and getattr(settings, "TWILIO_AUTH_TOKEN", "")
        and getattr(settings, "TWILIO_FROM_NUMBER", "")
    )


def send_sms(to: str, body: str) -> bool:
    """Envoie un SMS. Renvoie True si réellement envoyé, False en mode stub/erreur."""
    if not to:
        return False
    if not is_configured():
        logger.info("SMS (stub, Twilio non configuré) → %s : %s", to, body)
        return False
    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(to=to, from_=settings.TWILIO_FROM_NUMBER, body=body)
        return True
    except Exception as exc:  # pragma: no cover - dépend du réseau Twilio
        logger.warning("Échec envoi SMS à %s : %s", to, exc)
        return False
