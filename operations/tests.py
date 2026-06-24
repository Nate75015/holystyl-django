"""Tests opérations : machines/interventions API + intent IA creer_intervention."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from interventions.models import Intervention
from operations.models import Machine
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="op@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Op")
    return user, exploitation


@pytest.mark.django_db
def test_machine_api_create_scoped(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.post("/api/machines/", {"name": "Tracteur JD", "type": "tractor"}, content_type="application/json")
    assert resp.status_code == 201
    assert Machine.objects.get(name="Tracteur JD").exploitation == exploitation


@pytest.mark.django_db
def test_intervention_api_sets_user_and_scope(client, setup):
    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Sud")
    client.force_login(user)
    resp = client.post(
        "/api/interventions/",
        {"intervention_type": "taille", "parcelle": parcelle.id, "start_time": "2026-06-23T08:00:00Z"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    iv = Intervention.objects.get(parcelle=parcelle)
    assert iv.user == user and iv.exploitation == exploitation


@pytest.mark.django_db
def test_ai_intent_creates_intervention(setup, monkeypatch):
    from ia import services

    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", culture="abricotier")
    monkeypatch.setattr(services.gemini, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.gemini, "generate_json",
        lambda messages, **kw: {
            "response": "Intervention créée", "intent": "creer_intervention", "needs_more_info": False,
            "data": {"interventionType": "taille", "parcelleName": "Nord", "title": "Taille abricotiers"},
        },
    )
    result = services.execute_intent(exploitation, user, "Taille des abricotiers parcelle Nord")
    assert result["created"] is True and result["entity"]["type"] == "intervention"
    iv = Intervention.objects.get(exploitation=exploitation)
    assert iv.parcelle == parcelle and iv.intervention_type == "taille" and iv.source == "ai"


@pytest.mark.django_db
def test_catalogue_engins_readonly(client, setup):
    user, _ = setup
    client.force_login(user)
    # Lecture OK (référentiel global, vide ici)
    assert client.get("/api/catalogue-engins/").status_code == 200
    # Écriture interdite (ReadOnly)
    assert client.post("/api/catalogue-engins/", {"marque": "X", "modele": "Y", "type": "tracteur"},
                       content_type="application/json").status_code == 405
