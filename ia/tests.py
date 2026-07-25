"""Tests assistant IA : repli non-configuré + extraction d'intentions (Gemini mocké)."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from ia import services
from ia.models import AiConversation
from irrigation.models import IrrigationSession
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def user_exploitation(db):
    user = User.objects.create_user(email="ia@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme IA")
    return user, exploitation


@pytest.mark.django_db
def test_chat_not_configured_returns_message(user_exploitation, monkeypatch):
    user, exploitation = user_exploitation
    monkeypatch.setattr(services.llm, "is_configured", lambda: False)
    answer = services.chat(exploitation, user, "Bonjour")
    assert "configuré" in answer.lower()  # message « non configuré »
    # user + assistant persistés
    assert AiConversation.objects.filter(exploitation=exploitation).count() == 2


@pytest.mark.django_db
def test_execute_intent_creates_parcelle(user_exploitation, monkeypatch):
    user, exploitation = user_exploitation
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda messages, **kw: {
            "response": "Parcelle créée ✅", "intent": "creer_parcelle",
            "needs_more_info": False, "data": {"name": "Le Clos", "areaHa": 1.8, "culture": "Vigne"},
        },
    )
    result = services.execute_intent(exploitation, user, "Crée la parcelle Le Clos, 1.8 ha de vigne")
    assert result["created"] is True
    assert result["entity"]["type"] == "parcelle"
    p = Parcelle.objects.get(name="Le Clos")
    assert p.area == 1.8
    assert p.campagne_courante is not None and p.campagne_courante.culture == "Vigne"


@pytest.mark.django_db
def test_execute_intent_creates_irrigation_session(user_exploitation, monkeypatch):
    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord")
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda messages, **kw: {
            "response": "Session enregistrée", "intent": "creer_session_irrigation",
            "needs_more_info": False, "data": {"parcelleName": "Nord", "volumeDeliveredM3": 12.5},
        },
    )
    result = services.execute_intent(exploitation, user, "Irrigation 12.5 m³ sur les abricotiers")
    assert result["created"] is True
    session = IrrigationSession.objects.get(parcelle=parcelle)
    assert session.volume_delivered_m3 == 12.5
    assert session.triggered_by == IrrigationSession.TriggeredBy.AI


@pytest.mark.django_db
def test_execute_intent_unmigrated_module_is_graceful(user_exploitation, monkeypatch):
    user, exploitation = user_exploitation
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda messages, **kw: {"response": "", "intent": "creer_entretien", "needs_more_info": False, "data": {}},
    )
    result = services.execute_intent(exploitation, user, "Note un entretien sur le tracteur")
    assert result["created"] is False
    assert "version" in result["response"].lower() or result["response"]


@pytest.mark.django_db
def test_stream_endpoint_not_configured(client, user_exploitation, monkeypatch):
    user, _ = user_exploitation
    monkeypatch.setattr("ia.views.llm.is_configured", lambda: False)
    client.force_login(user)
    resp = client.get("/assistant/stream/", {"message": "Salut"})
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content).decode()
    assert "data:" in body and "done" in body


@pytest.mark.django_db
def test_reformuler_returns_ai_text(client, user_exploitation, monkeypatch):
    from ia import views

    user, _exploitation = user_exploitation
    monkeypatch.setattr(views.llm, "is_configured", lambda: True)
    monkeypatch.setattr(views.llm, "generate_text", lambda messages, **kw: '"Parcelle irriguée le 12 juin."')
    client.force_login(user)

    resp = client.post("/assistant/reformuler/", {"text": "arosé la parcelle le 12", "contexte": "Notes"})
    assert resp.status_code == 200
    assert resp.json()["text"] == "Parcelle irriguée le 12 juin."


@pytest.mark.django_db
def test_reformuler_requires_text_and_configured_ai(client, user_exploitation, monkeypatch):
    from ia import views

    user, _exploitation = user_exploitation
    client.force_login(user)

    assert client.post("/assistant/reformuler/", {"text": "  "}).status_code == 400

    monkeypatch.setattr(views.llm, "is_configured", lambda: False)
    assert client.post("/assistant/reformuler/", {"text": "un texte"}).status_code == 503
