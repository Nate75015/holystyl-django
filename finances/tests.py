"""Tests finances : charges/revenus, bilan ROI, factures TVA, exports, intents IA."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from exploitations.models import Exploitation
from finances.models import Charge, Facture, Revenu
from finances.services import compute_bilan
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="fi@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Fi", total_area=10)
    return user, exploitation


@pytest.mark.django_db
def test_bilan_roi_computation(setup):
    user, exploitation = setup
    Parcelle.objects.create(exploitation=exploitation, name="A", area=5)
    Revenu.objects.create(exploitation=exploitation, date=timezone.now(), categorie="vente_fruits", montant=10000)
    Charge.objects.create(exploitation=exploitation, date=timezone.now(), categorie="engrais", montant=3000)
    bilan = compute_bilan(exploitation)
    assert bilan.total_revenus == 10000 and bilan.total_charges == 3000
    assert bilan.resultat_net == 7000 and bilan.marge_par_ha == 1400  # 7000 / 5 ha


@pytest.mark.django_db
def test_facture_tva_computed(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.post(
        "/api/factures/",
        {"numero": "FAC-2026-001", "date_emission": "2026-06-23T00:00:00Z", "montant_ht": 1000, "taux_tva": 20},
        content_type="application/json",
    )
    assert resp.status_code == 201
    facture = Facture.objects.get(numero="FAC-2026-001")
    assert facture.montant_tva == 200 and facture.montant_ttc == 1200


@pytest.mark.django_db
def test_csv_export(client, setup):
    user, exploitation = setup
    Charge.objects.create(exploitation=exploitation, date=timezone.now(), categorie="eau", montant=500, fournisseur="Régie")
    client.force_login(user)
    resp = client.get("/reports/csv/?type=charges")
    assert resp.status_code == 200 and resp["Content-Type"] == "text/csv"
    body = resp.content.decode()
    assert "categorie" in body and "Régie" in body


@pytest.mark.django_db
def test_pdf_export(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.get("/reports/pdf/?type=taxonomie_verte&year=2026")
    # 200 + PDF si WeasyPrint dispo, sinon 501 (dépend des libs système)
    assert resp.status_code in (200, 501)
    if resp.status_code == 200:
        assert resp["Content-Type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_ai_intent_creates_charge_and_revenu(setup, monkeypatch):
    from ia import services

    user, exploitation = setup
    monkeypatch.setattr(services.gemini, "is_configured", lambda: True)

    monkeypatch.setattr(
        services.gemini, "generate_json",
        lambda m, **k: {"response": "Charge notée", "intent": "creer_charge", "needs_more_info": False,
                        "data": {"categorie": "engrais", "montant": 150, "fournisseur": "Yara"}},
    )
    r1 = services.execute_intent(exploitation, user, "Note une charge engrais de 150€ chez Yara")
    assert r1["entity"]["type"] == "charge"
    assert Charge.objects.filter(exploitation=exploitation, montant=150).exists()

    monkeypatch.setattr(
        services.gemini, "generate_json",
        lambda m, **k: {"response": "Vente notée", "intent": "creer_revenu", "needs_more_info": False,
                        "data": {"categorie": "vente_fruits", "montant": 2000, "acheteur": "Coop"}},
    )
    r2 = services.execute_intent(exploitation, user, "Vente de fruits 2000€ à la coop")
    assert r2["entity"]["type"] == "revenu"
    assert Revenu.objects.filter(exploitation=exploitation, montant=2000).exists()
