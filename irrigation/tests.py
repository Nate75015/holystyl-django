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


# ── Le bilan d'eau a rejoint le DTI ──────────────────────────────────


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="irr@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Irr")
    return user, exploitation


@pytest.mark.django_db
def test_le_dti_porte_aussi_le_bilan_d_eau(client, setup):
    """Diagnostic et bilan répondent à la même question : une seule page."""
    user, _exploitation = setup
    client.force_login(user)
    resp = client.get("/dti/")
    assert resp.status_code == 200
    html = resp.content.decode()

    assert "Diagnostic technique d'irrigation" in html   # le diagnostic…
    assert "Bilan d'eau" in html                          # …et le bilan
    assert "Irrigation totale" in html and "Quota" in html
    assert "/dti/bilan-eau/export/" in html
    # Les données du bilan sont bien dans le contexte de la page DTI.
    for cle in ("total_m3", "quota", "pct_quota", "cout", "monthly_chart", "parcelle_charts"):
        assert cle in resp.context
    assert "{#" not in html and "{{" not in html


@pytest.mark.django_db
def test_l_ancienne_adresse_redirige_sans_casser_les_liens(client, setup):
    """Un signet ou un lien partagé doit continuer de mener quelque part."""
    user, _exploitation = setup
    client.force_login(user)

    resp = client.get("/environnement/bilan-eau/")
    assert resp.status_code == 301 and resp["Location"] == "/dti/"

    resp = client.get("/environnement/bilan-eau/export/")
    assert resp.status_code == 301 and resp["Location"] == "/dti/bilan-eau/export/"


@pytest.mark.django_db
def test_l_export_csv_suit_le_deplacement(client, setup):
    from irrigation.models import IrrigationSession
    from parcelles.models import Parcelle

    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Le Clos")
    IrrigationSession.objects.create(
        exploitation=exploitation, parcelle=parcelle,
        start_time="2026-06-24T06:00:00Z", volume_delivered_m3=42.5)

    client.force_login(user)
    resp = client.get("/dti/bilan-eau/export/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    corps = resp.content.decode()
    assert "Le Clos" in corps and "42.5" in corps
    assert "Volume (m³)" in corps


@pytest.mark.django_db
def test_le_bilan_calcule_le_quota_et_le_cout(setup):
    from irrigation.bilan_eau import PRIX_EAU_PAR_DEFAUT_M3, QUOTA_PAR_DEFAUT_M3, donnees
    from irrigation.models import IrrigationSession

    _user, exploitation = setup
    IrrigationSession.objects.create(
        exploitation=exploitation, start_time="2026-06-24T06:00:00Z", volume_delivered_m3=1000)
    IrrigationSession.objects.create(
        exploitation=exploitation, start_time="2026-07-02T06:00:00Z", volume_delivered_m3=500)

    d = donnees(exploitation)
    assert d["total_m3"] == 1500 and d["nb_sessions"] == 2
    assert d["quota"] == QUOTA_PAR_DEFAUT_M3
    assert d["cout"] == round(1500 * PRIX_EAU_PAR_DEFAUT_M3)
    # Deux mois distincts, donc deux barres.
    assert d["monthly_chart"]["labels"] == ["06/2026", "07/2026"]
