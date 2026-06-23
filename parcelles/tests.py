"""Tests parcelles : CRUD web + API + isolation multi-tenant."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from exploitations.models import Exploitation
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def user_exploitation(db):
    user = User.objects.create_user(email="a@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme A", total_area=10)
    return user, exploitation


@pytest.mark.django_db
def test_create_parcelle_web(client, user_exploitation):
    user, exploitation = user_exploitation
    client.force_login(user)
    resp = client.post(
        reverse("parcelles:create"),
        {"name": "Nord", "area": 2.5, "kc_value": 1.0, "status": "active"},
    )
    assert resp.status_code == 302
    parcelle = Parcelle.objects.get(name="Nord")
    assert parcelle.exploitation == exploitation


@pytest.mark.django_db
def test_create_requires_onboarding(client):
    user = User.objects.create_user(email="b@ex.com", password="pwd12345")
    client.force_login(user)
    resp = client.get(reverse("parcelles:create"))
    assert resp.status_code == 302
    assert reverse("exploitations:settings") in resp.url


@pytest.mark.django_db
def test_api_list_is_tenant_scoped(client, user_exploitation):
    user, exploitation = user_exploitation
    Parcelle.objects.create(exploitation=exploitation, name="P1")
    # Autre utilisateur / autre exploitation
    other = User.objects.create_user(email="c@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Ferme C")
    Parcelle.objects.create(exploitation=other_exp, name="P2")

    client.force_login(user)
    resp = client.get("/api/parcelles/")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"P1"}  # P2 (autre tenant) absente


@pytest.mark.django_db
def test_api_create_attaches_exploitation(client, user_exploitation):
    user, exploitation = user_exploitation
    client.force_login(user)
    resp = client.post("/api/parcelles/", {"name": "Sud", "kc_value": 1.0}, content_type="application/json")
    assert resp.status_code == 201
    assert Parcelle.objects.get(name="Sud").exploitation == exploitation


@pytest.mark.django_db
def test_detail_404_cross_tenant(client, user_exploitation):
    user, exploitation = user_exploitation
    other = User.objects.create_user(email="d@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Ferme D")
    p = Parcelle.objects.create(exploitation=other_exp, name="Secrète")
    client.force_login(user)
    resp = client.get(reverse("parcelles:detail", args=[p.pk]))
    assert resp.status_code == 404
