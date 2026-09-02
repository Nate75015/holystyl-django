"""Tests administration : sauvegarde config SMTP via API + intent IA entretien."""

import pytest
from django.contrib.auth import get_user_model

from administration.models import SmtpConfig
from exploitations.models import Exploitation
from operations.models import EntretienMateriel, Machine

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="ad@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Ad")
    return user, exploitation


@pytest.mark.django_db
def test_smtp_config_save_via_api(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.put(
        "/api/admin/smtp/",
        {"host": "smtp.example.com", "port": 587, "user": "u@ex.com", "password": "secret", "from_email": "no@ex.com"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    cfg = SmtpConfig.objects.get(exploitation=exploitation)
    assert cfg.host == "smtp.example.com"
    # Le mot de passe est write-only (absent de la réponse)
    assert "password" not in resp.json()


@pytest.mark.django_db
def test_ai_intent_creates_entretien(setup, monkeypatch):
    from ia import services

    user, exploitation = setup
    machine = Machine.objects.create(exploitation=exploitation, name="Tracteur", type="tracteur_standard")
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda m, **k: {"response": "Entretien noté", "intent": "creer_entretien", "needs_more_info": False,
                        "data": {"machineName": "Tracteur", "type": "vidange", "cout": 120}},
    )
    result = services.execute_intent(exploitation, user, "Vidange du tracteur, 120€")
    assert result["created"] is True and result["entity"]["type"] == "entretien"
    assert EntretienMateriel.objects.filter(machine=machine, type="vidange").exists()
