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


# ── Qui voit le planning, et qui y écrit ─────────────────────────────


@pytest.fixture
def ferme_avec_salarie(db):
    """Un patron, un salarié rattaché, et une tâche assignée à ce salarié."""
    from equipe.models import Task, TeamMember

    patron = User.objects.create_user(email="patron@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=patron, name="Ferme du Test")
    salarie = User.objects.create_user(email="salarie@ex.com", password="pwd12345")
    membre = TeamMember.objects.create(exploitation=exploitation, name="Paul", user=salarie)
    tache = Task.objects.create(
        exploitation=exploitation, title="Taille des abricotiers", assigned_to=membre,
        start_date="2026-06-24T08:00:00Z", due_date="2026-06-24T18:00:00Z")
    return patron, salarie, exploitation, membre, tache


@pytest.mark.django_db
def test_le_salarie_voit_le_planning_de_sa_ferme(client, ferme_avec_salarie):
    """Il tombait sur l'écran vide alors que la tâche lui était assignée."""
    _patron, salarie, _exploitation, _membre, _tache = ferme_avec_salarie
    client.force_login(salarie)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Taille des abricotiers" in html
    assert "Ajoutez un membre d'équipe" not in html


@pytest.mark.django_db
def test_le_salarie_ecrit_aussi(client, ferme_avec_salarie):
    """L'agenda est commun : qui le lit le modifie, quel que soit son rôle."""
    from equipe.models import Task

    _patron, salarie, exploitation, membre, tache = ferme_avec_salarie
    client.force_login(salarie)

    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert '@click="openChoix(' in html

    assert client.post("/planning/taches/nouvelle/", {
        "title": "Binage rang 4", "assigned_to": str(membre.pk),
        "start_date": "2026-06-25", "vue": "semaine"}).status_code == 302
    assert Task.objects.filter(exploitation=exploitation, title="Binage rang 4").exists()

    # La tâche qu'on lui a assignée, il la modifie aussi.
    assert client.post(f"/planning/taches/{tache.pk}/modifier/", {
        "title": "Taille des abricotiers — reportée", "assigned_to": str(membre.pk),
        "start_date": "2026-06-26", "vue": "semaine"}).status_code == 302
    tache.refresh_from_db()
    assert tache.title == "Taille des abricotiers — reportée"


@pytest.mark.django_db
def test_sans_rattachement_on_n_ecrit_pas(client, db):
    """Le seul refus : qui n'appartient à aucune exploitation."""
    from equipe.models import Task

    isole = User.objects.create_user(email="isole@ex.com", password="pwd12345")
    client.force_login(isole)
    assert client.post("/planning/taches/nouvelle/", {"title": "Rien"}).status_code == 403
    assert client.post("/planning/reservations/nouvelle/", {"start": "2026-06-25"}).status_code == 403
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_le_patron_garde_la_main(client, ferme_avec_salarie):
    patron, _salarie, _exploitation, membre, _tache = ferme_avec_salarie
    client.force_login(patron)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert '@click="openChoix(' in html
    assert client.post("/planning/taches/nouvelle/", {
        "title": "Semis", "assigned_to": str(membre.pk),
        "start_date": "2026-06-25", "vue": "semaine"}).status_code == 302


# ── CUMA : ce que voient les fermes co-adhérentes ────────────────────


@pytest.fixture
def deux_fermes_une_cuma(db):
    """Deux exploitations ayant enregistré la même CUMA, au même SIRET.

    L'une possède une moissonneuse détenue en CUMA et la réserve.
    """
    from client.models import Partenaire
    from equipe.models import TeamMember
    from operations.models import AffectationEngin, Machine

    SIRET = "84219876500017"
    fermes = {}
    for cle, email, nom, siret in (
        ("a", "a@ex.com", "Ferme A", SIRET),
        ("b", "b@ex.com", "Ferme B", "842 198 765 00017"),   # même SIRET, autrement écrit
        ("c", "c@ex.com", "Ferme C", "39876543200011"),      # une autre CUMA
    ):
        u = User.objects.create_user(email=email, password="pwd12345")
        e = Exploitation.objects.create(owner=u, name=nom)
        TeamMember.objects.create(exploitation=e, name=nom, user=u)
        Partenaire.objects.create(exploitation=e, type_partenaire=Partenaire.Type.CUMA,
                                  nom="CUMA des Dentelles", siret=siret)
        fermes[cle] = (u, e)

    _ua, ferme_a = fermes["a"]
    cuma_a = Partenaire.objects.get(exploitation=ferme_a)
    moissonneuse = Machine.objects.create(
        exploitation=ferme_a, name="Claas Lexion", type="moissonneuse_batteuse",
        detention=Machine.Detention.CUMA, proprietaire=cuma_a)
    AffectationEngin.objects.create(
        exploitation=ferme_a, machine=moissonneuse, operation="recolte",
        date_debut="2026-06-24T00:00:00Z", date_fin="2026-06-25T00:00:00Z")
    return fermes


@pytest.mark.django_db
def test_un_co_adherent_voit_la_reservation_de_la_cuma(client, deux_fermes_une_cuma):
    """Le SIRET, même écrit avec des espaces, relie les deux fermes."""
    ub, _ferme_b = deux_fermes_une_cuma["b"]
    client.force_login(ub)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Claas Lexion" in html
    assert "Ferme A" in html          # on sait qui l'a prise…
    # …mais on ne la modifie pas : elle n'est pas à nous.
    assert '@click.stop="openEditReservation(' not in html


@pytest.mark.django_db
def test_une_ferme_d_une_autre_cuma_ne_voit_rien(client, deux_fermes_une_cuma):
    uc, _ferme_c = deux_fermes_une_cuma["c"]
    client.force_login(uc)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Claas Lexion" not in html and "Ferme A" not in html


@pytest.mark.django_db
def test_le_proprietaire_modifie_toujours_la_sienne(client, deux_fermes_une_cuma):
    ua, _ferme_a = deux_fermes_une_cuma["a"]
    client.force_login(ua)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Claas Lexion" in html
    assert '@click.stop="openEditReservation(' in html


@pytest.mark.django_db
def test_le_materiel_en_propre_ne_traverse_pas(client, deux_fermes_une_cuma):
    """Seul ce qui est détenu en CUMA franchit la frontière entre fermes."""
    from operations.models import AffectationEngin, Machine

    _ua, ferme_a = deux_fermes_une_cuma["a"]
    tracteur = Machine.objects.create(
        exploitation=ferme_a, name="Fendt en propre", type="tracteur_standard")
    AffectationEngin.objects.create(
        exploitation=ferme_a, machine=tracteur, operation="labour",
        date_debut="2026-06-24T00:00:00Z")

    ub, _ferme_b = deux_fermes_une_cuma["b"]
    client.force_login(ub)
    html = client.get("/planning/?vue=semaine&date=2026-06-24").content.decode()
    assert "Claas Lexion" in html          # le matériel de la CUMA, oui
    assert "Fendt en propre" not in html   # le reste de la ferme A, non


# ── Chevauchements : un engin ne se prend pas deux fois ──────────────


@pytest.mark.django_db
@pytest.mark.parametrize("debut,fin,attendu", [
    ("2026-06-26", "2026-06-27", True),   # commence pendant
    ("2026-06-22", "2026-06-25", True),   # finit pendant
    ("2026-06-20", "2026-06-30", True),   # englobe
    ("2026-06-25", "2026-06-26", True),   # à l'intérieur
    ("2026-06-24", "2026-06-24", True),   # accolée au premier jour
    ("2026-06-28", "2026-06-28", True),   # accolée au dernier jour
    ("2026-06-29", "2026-06-30", False),  # juste après
    ("2026-06-22", "2026-06-23", False),  # juste avant
])
def test_un_engin_deja_pris_est_refuse(client, setup, parc, debut, fin, attendu):
    """Une réservation du 24 au 28 : tout ce qui la touche est refusé."""
    from operations.models import AffectationEngin

    user, exploitation = setup
    _e, machine = parc
    client.force_login(user)
    AffectationEngin.objects.create(
        exploitation=exploitation, machine=machine, operation="recolte",
        date_debut="2026-06-24T00:00:00Z", date_fin="2026-06-28T00:00:00Z")

    client.post("/planning/reservations/nouvelle/", {
        "machine": str(machine.pk), "start": debut, "end": fin, "vue": "semaine"})
    refusee = AffectationEngin.objects.count() == 1
    assert refusee is attendu


@pytest.mark.django_db
def test_le_refus_dit_qui_occupe_l_engin(client, setup, parc):
    from operations.models import AffectationEngin

    user, exploitation = setup
    _e, machine = parc
    client.force_login(user)
    AffectationEngin.objects.create(
        exploitation=exploitation, machine=machine, operation="recolte",
        date_debut="2026-06-24T00:00:00Z", date_fin="2026-06-28T00:00:00Z")

    resp = client.post("/planning/reservations/nouvelle/", {
        "machine": str(machine.pk), "start": "2026-06-25", "vue": "semaine"}, follow=True)
    messages = [str(m) for m in resp.context["messages"]]
    assert any("Fendt 313" in m and "Récolte" in m for m in messages)


@pytest.mark.django_db
def test_deplacer_une_reservation_ne_la_heurte_pas_elle_meme(client, setup, parc):
    """Elle s'exclut du calcul, sinon on ne pourrait jamais la décaler."""
    from operations.models import AffectationEngin

    user, exploitation = setup
    _e, machine = parc
    client.force_login(user)
    r = AffectationEngin.objects.create(
        exploitation=exploitation, machine=machine, operation="recolte",
        date_debut="2026-06-24T00:00:00Z", date_fin="2026-06-28T00:00:00Z")

    assert client.post(f"/planning/reservations/{r.pk}/modifier/", {
        "machine": str(machine.pk), "operation": "recolte",
        "start": "2026-06-25", "end": "2026-06-29", "vue": "semaine"}).status_code == 302
    r.refresh_from_db()
    assert str(timezone.localdate(r.date_fin)) == "2026-06-29"


@pytest.mark.django_db
def test_deux_engins_differents_ne_se_gênent_pas(client, setup, parc):
    from operations.models import AffectationEngin, Machine

    user, exploitation = setup
    _e, machine = parc
    autre = Machine.objects.create(
        exploitation=exploitation, name="Claas Lexion", type="moissonneuse_batteuse")
    client.force_login(user)
    AffectationEngin.objects.create(
        exploitation=exploitation, machine=machine, operation="recolte",
        date_debut="2026-06-24T00:00:00Z", date_fin="2026-06-28T00:00:00Z")

    client.post("/planning/reservations/nouvelle/", {
        "machine": str(autre.pk), "start": "2026-06-25", "end": "2026-06-26", "vue": "semaine"})
    assert AffectationEngin.objects.count() == 2
