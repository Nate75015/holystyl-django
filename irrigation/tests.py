"""Tests irrigation : moteur DTI + API tenant-scoped."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from irrigation.models import DtiScore, IrrigationZone
from irrigation.services import calculate_dti_score
from parcelles.models import Parcelle

User = get_user_model()


@pytest.mark.parametrize(
    "kwh,expected",
    [(0.20, "A"), (0.24, "A"), (0.30, "B"), (0.40, "C"), (0.60, "D")],
)
def test_dti_score_boundaries(kwh, expected):
    assert calculate_dti_score(kwh).score == expected


def test_dti_numeric_capped_and_recommendations():
    result = calculate_dti_score(0.10, uniformity=80)
    assert result.numeric <= 100
    assert any("Uniformité" in r for r in result.recommendations)


@pytest.mark.django_db
def test_dti_calculate_endpoint_persists(client):
    user = User.objects.create_user(email="dti@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="F")
    client.force_login(user)
    resp = client.post("/api/dti/calculate/", {"kwhPerM3": 0.22, "uniformity": 92}, content_type="application/json")
    assert resp.status_code == 200
    assert resp.json()["score"] == "A"
    assert DtiScore.objects.filter(exploitation=exploitation, score="A").exists()


@pytest.mark.django_db
def test_irrigation_zone_api_create_scoped(client):
    user = User.objects.create_user(email="z@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="F")
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="P1")
    client.force_login(user)
    resp = client.post(
        "/api/irrigation/zones/",
        {"parcelle": parcelle.id, "name": "Zone A", "irrigation_type": "goutte_a_goutte"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    zone = IrrigationZone.objects.get(name="Zone A")
    assert zone.exploitation == exploitation
