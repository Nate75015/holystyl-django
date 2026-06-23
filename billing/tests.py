"""Tests billing : génération/activation de code, webhook Stripe."""

import json

import pytest
from django.contrib.auth import get_user_model

from billing.models import ActivationCode
from billing.services import activate_code, generate_activation_code
from exploitations.models import Exploitation

User = get_user_model()


@pytest.mark.django_db
def test_generate_code_format_and_unique():
    code = generate_activation_code()
    assert code.startswith("HOLS-") and len(code) == 14  # HOLS-XXXX-XXXX


@pytest.mark.django_db
def test_activate_code_flow():
    user = User.objects.create_user(email="b@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="F")
    code = ActivationCode.objects.create(code="HOLS-AAAA-BBBB", email="b@ex.com")
    activated = activate_code("HOLS-AAAA-BBBB", user, exploitation)
    assert activated is not None and activated.status == "used"
    # Un 2e appel échoue (déjà utilisé)
    assert activate_code("HOLS-AAAA-BBBB", user, exploitation) is None


@pytest.mark.django_db
def test_activation_verify_api(client):
    ActivationCode.objects.create(code="HOLS-CCCC-DDDD", email="x@ex.com")
    resp = client.get("/api/activation/verify/?code=HOLS-CCCC-DDDD")
    assert resp.json()["valid"] is True
    assert client.get("/api/activation/verify/?code=NOPE").json()["valid"] is False


@pytest.mark.django_db
def test_stripe_webhook_creates_activation(client, settings):
    settings.STRIPE_WEBHOOK_SECRET = ""  # mode dev : pas de vérification de signature
    payload = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_1", "customer_details": {"email": "buyer@ex.com"}, "subscription": "sub_1"}},
    }
    resp = client.post("/api/stripe/webhook/", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    code = ActivationCode.objects.get(email="buyer@ex.com")
    assert code.stripe_subscription_id == "sub_1" and code.status == "pending"
