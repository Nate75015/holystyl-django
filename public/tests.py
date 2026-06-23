"""Tests public : landing, lead magnet, Alex, activation."""

import json

import pytest
from django.contrib.auth import get_user_model

from public.models import LeadCapture
from public import services

User = get_user_model()


@pytest.mark.django_db
def test_home_public_then_redirect_when_authenticated(client):
    assert client.get("/").status_code == 200  # anonyme : landing
    user = User.objects.create_user(email="h@ex.com", password="pwd12345")
    client.force_login(user)
    resp = client.get("/")
    assert resp.status_code == 302 and "/pulse/" in resp.url


@pytest.mark.django_db
def test_lead_capture(client):
    resp = client.post("/lead/", {"email": "prospect@ex.com"})
    assert resp.status_code == 302
    assert LeadCapture.objects.filter(email="prospect@ex.com").exists()


@pytest.mark.django_db
def test_alex_not_configured(client, monkeypatch):
    monkeypatch.setattr(services.gemini, "is_configured", lambda: False)
    resp = client.post("/alex/", data=json.dumps({"messages": [{"role": "user", "content": "Bonjour"}]}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "Alex" in resp.json()["response"]


@pytest.mark.django_db
def test_alex_configured_mocked(client, monkeypatch):
    monkeypatch.setattr(services.gemini, "is_configured", lambda: True)
    monkeypatch.setattr(services.gemini, "generate_text", lambda msgs, **k: "Ravi de vous aider !")
    resp = client.post("/alex/", data=json.dumps({"messages": [{"role": "user", "content": "C'est quoi le DTI ?"}]}),
                       content_type="application/json")
    assert resp.json()["response"] == "Ravi de vous aider !"
