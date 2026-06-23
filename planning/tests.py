"""Tests planning : logTime → statut, bon d'intervention, scoping."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from planning.models import InterventionReport, PlanningTask

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="pl@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Pl")
    return user, exploitation


@pytest.mark.django_db
def test_log_time_updates_status(client, setup):
    user, exploitation = setup
    task = PlanningTask.objects.create(exploitation=exploitation, titre="Taille", statut="planifie")
    client.force_login(user)
    resp = client.post(f"/api/planning/tasks/{task.id}/log-time/", {"action": "start"}, content_type="application/json")
    assert resp.status_code == 200
    task.refresh_from_db()
    assert task.statut == "en_cours"

    client.post(f"/api/planning/tasks/{task.id}/log-time/", {"action": "complete"}, content_type="application/json")
    task.refresh_from_db()
    assert task.statut == "termine" and task.completed_at is not None


@pytest.mark.django_db
def test_planning_stats(client, setup):
    user, exploitation = setup
    PlanningTask.objects.create(exploitation=exploitation, titre="A", statut="planifie", is_backlog=False)
    PlanningTask.objects.create(exploitation=exploitation, titre="B", statut="termine", is_backlog=True)
    client.force_login(user)
    stats = client.get("/api/planning/tasks/stats/").json()
    assert stats["total"] == 2 and stats["termine"] == 1 and stats["backlog"] == 1


@pytest.mark.django_db
def test_bon_intervention_creates_and_validates(client, setup):
    user, exploitation = setup
    task = PlanningTask.objects.create(exploitation=exploitation, titre="Traitement", technicien_nom="Aude")
    client.force_login(user)
    # GET crée le bon en brouillon
    assert client.get(f"/bon-intervention/{task.id}/").status_code == 200
    assert InterventionReport.objects.filter(planning_task=task).exists()
    # POST validation
    resp = client.post(
        f"/bon-intervention/{task.id}/",
        {"action": "validate", "description_travaux": "Taille effectuée", "produits_utilises": "[]"},
    )
    assert resp.status_code == 302
    report = InterventionReport.objects.get(planning_task=task)
    assert report.statut == "valide" and report.description_travaux == "Taille effectuée"


@pytest.mark.django_db
def test_report_api_validate_action(client, setup):
    user, exploitation = setup
    task = PlanningTask.objects.create(exploitation=exploitation, titre="X")
    report = InterventionReport.objects.create(exploitation=exploitation, planning_task=task, titre="X")
    client.force_login(user)
    resp = client.post(f"/api/planning/reports/{report.id}/validate/")
    assert resp.status_code == 200
    report.refresh_from_db()
    assert report.statut == "valide"
