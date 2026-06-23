"""Webhook Stripe (parité server/stripe-webhook.ts).

Events : checkout.session.completed (→ code d'activation + email),
customer.subscription.deleted, invoice.payment_failed (→ alerte admin).
"""

import json
import logging

from django.conf import settings
from django.core.mail import mail_admins
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import create_activation_for_purchase

logger = logging.getLogger("holystyl.stripe")


def _verify_event(request):
    """Vérifie la signature Stripe si configurée ; sinon parse le JSON brut (dev)."""
    payload = request.body
    sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    if settings.STRIPE_WEBHOOK_SECRET:
        import stripe

        return stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    return json.loads(payload or "{}")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = _verify_event(request)
    except Exception as exc:  # signature invalide / payload illisible
        logger.warning("Webhook Stripe rejeté : %s", exc)
        return HttpResponse(status=400)

    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    obj = (event.get("data", {}) or {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

    if event_type == "checkout.session.completed":
        email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email")
        if email:
            create_activation_for_purchase(
                email,
                session_id=obj.get("id", ""),
                customer_id=obj.get("customer", "") or "",
                subscription_id=obj.get("subscription", "") or "",
            )
        else:
            logger.warning("checkout.session.completed sans email : %s", obj.get("id"))

    elif event_type == "customer.subscription.deleted":
        mail_admins("Résiliation Holystyl", f"Abonnement résilié : {obj.get('id')}", fail_silently=True)

    elif event_type == "invoice.payment_failed":
        mail_admins("Paiement échoué Holystyl", f"Facture en échec : {obj.get('id')}", fail_silently=True)

    return JsonResponse({"received": True})
