"""Tests notifications : API CRUD, mark-read, compteur, scoping utilisateur."""

import pytest
from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.services import notify

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="notif@ex.com", password="pwd12345")


@pytest.mark.django_db
def test_notify_creates(user):
    n = notify(user, type="alert", title="Fuite", message="Débit anormal", priority="haute")
    assert n.pk and n.read is False


@pytest.mark.django_db
def test_unread_count_and_mark_all(client, user):
    notify(user, type="a", title="1", message="m")
    notify(user, type="a", title="2", message="m")
    client.force_login(user)
    assert client.get("/api/notifications/unread-count/").json()["count"] == 2
    resp = client.post("/api/notifications/mark-all-read/")
    assert resp.json()["updated"] == 2
    assert client.get("/api/notifications/unread-count/").json()["count"] == 0


@pytest.mark.django_db
def test_mark_single_read(client, user):
    n = notify(user, type="a", title="x", message="m")
    client.force_login(user)
    resp = client.post(f"/api/notifications/{n.id}/mark-read/")
    assert resp.status_code == 200
    n.refresh_from_db()
    assert n.read is True


@pytest.mark.django_db
def test_notifications_user_scoped(client, user):
    other = User.objects.create_user(email="other@ex.com", password="pwd12345")
    notify(user, type="a", title="mine", message="m")
    notify(other, type="a", title="theirs", message="m")
    client.force_login(user)
    titles = {n["title"] for n in client.get("/api/notifications/").json()}
    assert titles == {"mine"}


@pytest.mark.django_db
def test_rule_toggle(client, user):
    client.force_login(user)
    created = client.post(
        "/api/notification-rules/",
        {"name": "Gel", "type": "frost", "condition_type": "below", "channels": ["email"]},
        content_type="application/json",
    ).json()
    resp = client.post(f"/api/notification-rules/{created['id']}/toggle/")
    assert resp.json()["enabled"] is False
