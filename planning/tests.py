"""Tests planning : logTime → statut, bon d'intervention, scoping."""

import pytest
from django.contrib.auth import get_user_model

from django.utils import timezone

from exploitations.models import Exploitation
from planning.models import InterventionReport, PlanningTask

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="pl@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Pl")
    return user, exploitation


@pytest.mark.django_db
def test_planning_week_grid_empty_state(client, setup):
    user, _ = setup
    client.force_login(user)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Équipe" in html
    assert "Ajoutez un membre d'équipe" in html  # état vide (pas de salarié)
    # Les 7 numéros de jour de la semaine (lun 22 → dim 28) sont rendus.
    for day in (22, 23, 24, 25, 26, 27, 28):
        assert f">{day}<" in html


@pytest.mark.django_db
def test_planning_week_navigation(client, setup):
    user, _ = setup
    client.force_login(user)
    # Semaine fixée : le lundi 2026-06-22 doit afficher les jours 22 et 28.
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert ">22<" in html and ">28<" in html
    # Navigation : la semaine précédente commence le lundi 15 juin.
    prec = client.get("/planning/?vue=semaine&date=2026-06-15").content.decode()
    assert ">15<" in prec and ">21<" in prec


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


# ── Réservation de matériel depuis l'agenda ──────────────────────────


@pytest.fixture
def parc(setup):
    """Un engin du parc, et un membre d'équipe pour que la grille s'affiche."""
    from equipe.models import TeamMember
    from operations.models import Machine

    _user, exploitation = setup
    TeamMember.objects.create(exploitation=exploitation, name="Paul")
    machine = Machine.objects.create(
        exploitation=exploitation, name="Fendt 313", type="tracteur_standard")
    return exploitation, machine


@pytest.mark.django_db
def test_le_clic_propose_un_choix_avant_la_tache(client, setup, parc):
    """Le pas d'avant : la cellule n'ouvre plus la tâche, elle demande quoi poser."""
    user, _exploitation = setup
    client.force_login(user)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()

    assert "openChoix(" in html          # la cellule passe par le choix…
    assert "Que planifier ?" in html
    assert "Créer une tâche" in html and "Réserver du matériel" in html
    # …et plus jamais directement par la création de tâche.
    assert "@click=\"openAdd(" not in html


@pytest.mark.django_db
def test_reserver_du_materiel(client, setup, parc):
    from operations.models import AffectationEngin

    user, exploitation = setup
    _exploitation, machine = parc
    client.force_login(user)

    resp = client.post("/planning/reservations/nouvelle/", {
        "machine": str(machine.pk), "operation": "labour",
        "start": "2026-06-24", "end": "2026-06-26",
        "notes": "Bloqué pour les labours du haut.", "vue": "semaine", "date": "2026-06-24"})
    assert resp.status_code == 302 and "vue=semaine" in resp["Location"]

    r = AffectationEngin.objects.get(machine=machine)
    assert r.exploitation == exploitation and r.created_by == user
    assert r.operation == "labour"
    assert r.parcelle is None            # la parcelle reste facultative
    # Minuit est posé en heure locale : on relit les dates de la même façon.
    assert str(timezone.localdate(r.date_debut)) == "2026-06-24"
    assert str(timezone.localdate(r.date_fin)) == "2026-06-26"

    # Elle apparaît dans l'agenda, dans sa propre bande.
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Matériel" in html and "Fendt 313" in html
    assert "openEditReservation(" in html
    # Un {# … #} à cheval sur deux lignes n'est pas un commentaire pour Django :
    # il s'affiche en clair. Aucun marqueur de gabarit ne doit atteindre la page.
    assert "{#" not in html and "#}" not in html


@pytest.mark.django_db
def test_reservation_sans_materiel_ou_sans_date_est_refusee(client, setup, parc):
    from operations.models import AffectationEngin

    user, _exploitation = setup
    _e, machine = parc
    client.force_login(user)

    client.post("/planning/reservations/nouvelle/", {"start": "2026-06-24"})
    client.post("/planning/reservations/nouvelle/", {"machine": str(machine.pk)})
    assert AffectationEngin.objects.count() == 0


@pytest.mark.django_db
def test_on_ne_reserve_pas_le_materiel_du_voisin(client, setup, parc):
    """Cloisonnement : l'engin d'une autre ferme n'est pas réservable."""
    from operations.models import AffectationEngin, Machine

    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin3@ex.com", password="pwd12345")
    ferme_voisine = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    engin_du_voisin = Machine.objects.create(
        exploitation=ferme_voisine, name="Claas du voisin", type="moissonneuse_batteuse")

    client.force_login(user)
    client.post("/planning/reservations/nouvelle/", {
        "machine": str(engin_du_voisin.pk), "start": "2026-06-24"})
    assert AffectationEngin.objects.count() == 0


@pytest.mark.django_db
def test_modifier_et_annuler_une_reservation(client, setup, parc):
    from operations.models import AffectationEngin

    user, exploitation = setup
    _e, machine = parc
    client.force_login(user)
    r = AffectationEngin.objects.create(
        exploitation=exploitation, machine=machine, operation="autre",
        date_debut="2026-06-24T00:00:00Z")

    client.post(f"/planning/reservations/{r.pk}/modifier/", {
        "machine": str(machine.pk), "operation": "recolte",
        "start": "2026-06-25", "end": "2026-06-25"})
    r.refresh_from_db()
    assert r.operation == "recolte" and str(timezone.localdate(r.date_debut)) == "2026-06-25"

    assert client.post(f"/planning/reservations/{r.pk}/supprimer/").status_code == 302
    assert not AffectationEngin.objects.filter(pk=r.pk).exists()


@pytest.mark.django_db
def test_les_dates_inversees_sont_remises_dans_l_ordre(client, setup, parc):
    from operations.models import AffectationEngin

    user, _exploitation = setup
    _e, machine = parc
    client.force_login(user)
    client.post("/planning/reservations/nouvelle/", {
        "machine": str(machine.pk), "start": "2026-06-26", "end": "2026-06-24"})
    r = AffectationEngin.objects.get()
    assert str(timezone.localdate(r.date_debut)) == "2026-06-24"
    assert str(timezone.localdate(r.date_fin)) == "2026-06-26"
