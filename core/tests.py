"""Tests du socle core."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_ok(client):
    resp = client.get(reverse("core:healthz"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Adresses : découpage de voie et autocomplétion ──────────────────

@pytest.mark.parametrize("libelle,attendu", [
    ("Rue des Vergers", ("rue", "des Vergers")),
    ("Avenue du Général Leclerc", ("avenue", "du Général Leclerc")),
    ("Bd Voltaire", ("boulevard", "Voltaire")),          # abréviation
    ("Rond-point de la Gare", ("rond_point", "de la Gare")),  # trait d'union
    ("Grande rue", ("grande_rue", "")),                  # catégorie en deux mots
    ("Le Clos Fleuri", ("", "Le Clos Fleuri")),          # catégorie inconnue
    ("", ("", "")),
])
def test_split_voie(libelle, attendu):
    from core.adresse import split_voie

    assert split_voie(libelle) == attendu


@pytest.mark.django_db
def test_adresse_suggestions_uses_ban_without_google_key(client, django_user_model, monkeypatch, settings):
    from core import adresse

    settings.GOOGLE_MAPS_API_KEY = ""
    monkeypatch.setattr(adresse, "_get_json", lambda url, **kw: {"features": [{"properties": {
        "id": "84007_5540_00012", "label": "12 Rue de la République 84000 Avignon",
        "housenumber": "12", "street": "Rue de la République", "postcode": "84000", "city": "Avignon",
    }}]})

    user = django_user_model.objects.create_user(email="adr@ex.com", password="pwd12345")
    client.force_login(user)

    data = client.get(reverse("core:adresse_suggestions"), {"q": "12 rue de la republique"}).json()
    assert data["fournisseur"] == "ban"
    assert data["results"][0]["adresse"] == {
        "numero_voie": "12", "type_voie": "rue", "voie": "de la République",
        "code_postal": "84000", "ville": "Avignon", "pays": "France",
    }


@pytest.mark.django_db
def test_adresse_suggestions_uses_google_when_key_set(client, django_user_model, monkeypatch, settings):
    from core import adresse

    settings.GOOGLE_MAPS_API_KEY = "cle-de-test"
    appels = []

    def faux_get_json(url, **kw):
        appels.append(url)
        if "autocomplete" in url:
            return {"suggestions": [{"placePrediction": {
                "placeId": "PLACE1", "text": {"text": "12 Rue de la République, Avignon"},
            }}]}
        return {"addressComponents": [
            {"types": ["street_number"], "longText": "12"},
            {"types": ["route"], "longText": "Rue de la République"},
            {"types": ["postal_code"], "longText": "84000"},
            {"types": ["locality"], "longText": "Avignon"},
            {"types": ["country"], "longText": "France"},
        ]}

    monkeypatch.setattr(adresse, "_get_json", faux_get_json)
    user = django_user_model.objects.create_user(email="adr2@ex.com", password="pwd12345")
    client.force_login(user)

    data = client.get(reverse("core:adresse_suggestions"), {"q": "12 rue de la republique"}).json()
    assert data["fournisseur"] == "google"
    # Google ne renvoie que des prédictions : les composants viennent d'un second appel.
    assert data["results"][0] == {"id": "PLACE1", "label": "12 Rue de la République, Avignon", "adresse": None}

    detail = client.get(reverse("core:adresse_details"), {"id": "PLACE1"}).json()
    assert detail["adresse"]["numero_voie"] == "12"
    assert detail["adresse"]["type_voie"] == "rue" and detail["adresse"]["voie"] == "de la République"
    assert detail["adresse"]["ville"] == "Avignon" and detail["adresse"]["pays"] == "France"


@pytest.mark.django_db
def test_adresse_suggestions_degrade_sans_reseau(client, django_user_model, monkeypatch, settings):
    """Fournisseur injoignable → liste vide, la saisie manuelle reste possible."""
    from core import adresse

    settings.GOOGLE_MAPS_API_KEY = ""

    def boom(url, **kw):
        raise OSError("réseau indisponible")

    monkeypatch.setattr(adresse, "_get_json", boom)
    user = django_user_model.objects.create_user(email="adr3@ex.com", password="pwd12345")
    client.force_login(user)

    resp = client.get(reverse("core:adresse_suggestions"), {"q": "avignon"})
    assert resp.status_code == 200 and resp.json()["results"] == []
