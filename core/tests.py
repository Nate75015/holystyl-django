"""Tests du socle core."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_ok(client):
    resp = client.get(reverse("core:healthz"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
