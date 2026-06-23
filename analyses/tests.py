"""Tests analyses : extraction OCR/IA (Gemini mocké), API sol."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from analyses import services
from analyses.models import AnalyseSol, AnalysisResult
from exploitations.models import Exploitation
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="an@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme An")
    return user, exploitation


@pytest.mark.django_db
def test_apply_extraction_not_configured_returns_false(setup, monkeypatch):
    user, exploitation = setup
    monkeypatch.setattr(services.gemini, "is_configured", lambda: False)
    report = AnalysisResult.objects.create(
        exploitation=exploitation, analysis_type="soil", sample_date=timezone.now(), ocr_raw_text="pH 6.8"
    )
    assert services.apply_extraction(report) is False
    report.refresh_from_db()
    assert report.status == "pending_ocr" and report.ph is None  # rien d'inventé


@pytest.mark.django_db
def test_apply_extraction_fills_values(setup, monkeypatch):
    user, exploitation = setup
    monkeypatch.setattr(services.gemini, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.gemini, "generate_json",
        lambda messages, **kw: {
            "ph": 6.8, "organicMatterPct": 2.1, "nitrogenMgKg": 1200,
            "phosphorusMgKg": 45, "potassiumMgKg": 210, "electricalConductivity": 0.3,
            "recommendations": "Apport de matière organique recommandé.",
        },
    )
    report = AnalysisResult.objects.create(
        exploitation=exploitation, analysis_type="soil", sample_date=timezone.now(),
        ocr_raw_text="Rapport analyse sol : pH 6.8 ...",
    )
    assert services.apply_extraction(report) is True
    report.refresh_from_db()
    assert report.ph == 6.8 and report.nitrogen_mg_kg == 1200 and report.status == "ocr_done"


@pytest.mark.django_db
def test_extract_endpoint(client, setup, monkeypatch):
    user, exploitation = setup
    monkeypatch.setattr("analyses.services.gemini.is_configured", lambda: True)
    monkeypatch.setattr("analyses.services.gemini.generate_json", lambda m, **k: {"ph": 7.0, "recommendations": "OK"})
    report = AnalysisResult.objects.create(exploitation=exploitation, analysis_type="soil", sample_date=timezone.now())
    client.force_login(user)
    resp = client.post(f"/api/analyses/lab/{report.id}/extract/", {"ocrRawText": "pH 7.0"}, content_type="application/json")
    assert resp.status_code == 200 and resp.json()["applied"] is True


@pytest.mark.django_db
def test_analyse_sol_api_scoped(client, setup):
    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="P")
    client.force_login(user)
    resp = client.post(
        "/api/analyses/sol/",
        {"parcelle": parcelle.id, "date": "2026-06-23T00:00:00Z", "ph": 6.5},
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert AnalyseSol.objects.get(parcelle=parcelle).exploitation == exploitation
