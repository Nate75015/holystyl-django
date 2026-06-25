"""Tests équipe : API tâches/membres, SMS d'affectation, rappels Celery, lien géoloc."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from equipe import services, tasks as celery_tasks
from equipe.models import Task, TeamMember
from exploitations.models import Exploitation

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="eq@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Eq")
    member = TeamMember.objects.create(exploitation=exploitation, name="Aude", phone="+33600000000", email="aude@ex.com")
    return user, exploitation, member


@pytest.mark.django_db
def test_create_task_sends_sms_on_assignment(client, setup, monkeypatch):
    user, exploitation, member = setup
    calls = {}
    monkeypatch.setattr("equipe.services.send_sms", lambda to, body: calls.update(to=to, body=body) or True)
    client.force_login(user)
    resp = client.post(
        "/api/tasks/",
        {"title": "Tailler parcelle nord", "assigned_to": member.id, "priority": "haute"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert calls.get("to") == "+33600000000"
    assert "Tailler" in calls.get("body", "")


@pytest.mark.django_db
def test_task_api_tenant_scoped(client, setup):
    user, exploitation, member = setup
    Task.objects.create(exploitation=exploitation, title="Mine")
    other = User.objects.create_user(email="o@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Autre")
    Task.objects.create(exploitation=other_exp, title="Theirs")
    client.force_login(user)
    titles = {t["title"] for t in client.get("/api/tasks/").json()}
    assert titles == {"Mine"}


@pytest.mark.django_db
def test_add_member_via_form(client, setup):
    user, exploitation, _ = setup
    client.force_login(user)
    resp = client.post(
        "/equipe/",
        {
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@exemple.fr",
            "phone": "+33 6 12 34 56 78",
            "role": "ouvrier",
            "password": "abcd",
            "preferred_locale": "fr",
            "modules": ["planning", "parcelles", "irrigation", "iot", "ia", "taches"],
        },
    )
    assert resp.status_code == 302
    m = TeamMember.objects.get(email="jean@exemple.fr")
    assert m.exploitation == exploitation and m.managed_by == user
    assert m.name == "Jean Dupont" and m.role == "ouvrier"
    assert m.allowed_modules == ["planning", "parcelles", "irrigation", "iot", "ia", "taches"]
    # Mot de passe stocké haché (jamais en clair) et vérifiable.
    from django.contrib.auth.hashers import check_password

    assert m.password_hash and m.password_hash != "abcd"
    assert check_password("abcd", m.password_hash)


@pytest.mark.django_db
def test_edit_member(client, setup):
    user, exploitation, member = setup  # member: Aude, ouvrier par défaut
    member.allowed_modules = ["planning"]
    member.password_hash = "OLDHASH"
    member.save()
    client.force_login(user)
    resp = client.post(
        f"/equipe/{member.id}/modifier/",
        {
            "first_name": "Aude",
            "last_name": "Lemaire",
            "email": "aude@ex.com",
            "phone": "+33611111111",
            "role": "chef",
            "password": "",  # vide → on garde le mot de passe actuel
            "preferred_locale": "en",
            "modules": ["planning", "irrigation"],
        },
    )
    assert resp.status_code == 302
    member.refresh_from_db()
    assert member.name == "Aude Lemaire"
    assert member.role == "chef"
    assert member.preferred_locale == "en"
    assert member.allowed_modules == ["planning", "irrigation"]
    assert member.password_hash == "OLDHASH"  # inchangé car mot de passe laissé vide


@pytest.mark.django_db
def test_edit_member_scoped_to_exploitation(client, setup):
    user, _, _ = setup
    other = User.objects.create_user(email="other@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Autre")
    foreign = TeamMember.objects.create(exploitation=other_exp, name="Pas à moi")
    client.force_login(user)
    assert client.get(f"/equipe/{foreign.id}/modifier/").status_code == 404


@pytest.mark.django_db
def test_add_member_rejects_short_password(client, setup):
    user, _, _ = setup
    client.force_login(user)
    resp = client.post(
        "/equipe/",
        {"first_name": "X", "last_name": "Y", "email": "x@ex.com", "role": "ouvrier", "password": "ab", "preferred_locale": "fr"},
    )
    assert resp.status_code == 200  # ré-affiché avec erreurs
    assert not TeamMember.objects.filter(email="x@ex.com").exists()


@pytest.mark.django_db
def test_location_link_generated(setup):
    _, _, member = setup
    token = services.generate_location_link(member)
    member.refresh_from_db()
    assert member.location_token == token
    assert member.location_token_expires_at > timezone.now()


@pytest.mark.django_db
def test_reminder_job_sets_flag_and_notifies(setup, monkeypatch):
    user, exploitation, member = setup
    sms = []
    monkeypatch.setattr("equipe.tasks.send_sms", lambda to, body: sms.append(to) or True)
    monkeypatch.setattr("equipe.tasks.send_mail", lambda *a, **k: 1)
    task = Task.objects.create(
        exploitation=exploitation, title="Arrosage", assigned_to=member,
        due_date=timezone.now() + timedelta(hours=24),
    )
    celery_tasks.check_task_reminders()
    task.refresh_from_db()
    assert task.reminder_sent_24h is True
    assert sms == ["+33600000000"]
