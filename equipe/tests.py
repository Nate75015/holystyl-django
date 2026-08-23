"""Tests équipe : API tâches/membres, SMS d'affectation, rappels Celery, lien géoloc."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from equipe import invitations, services, tasks as celery_tasks
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
        },
    )
    assert resp.status_code == 302
    m = TeamMember.objects.get(email="jean@exemple.fr")
    assert m.exploitation == exploitation and m.managed_by == user
    assert m.name == "Jean Dupont" and m.role == "ouvrier"


@pytest.mark.django_db
def test_edit_member(client, setup):
    user, exploitation, member = setup  # member: Aude, ouvrier par défaut
    client.force_login(user)
    resp = client.post(
        f"/equipe/{member.id}/modifier/",
        {
            "first_name": "Aude",
            "last_name": "Lemaire",
            "email": "aude@ex.com",
            "phone": "+33611111111",
            "role": "chef",
        },
    )
    assert resp.status_code == 302
    member.refresh_from_db()
    assert member.name == "Aude Lemaire"
    assert member.role == "chef"


@pytest.mark.django_db
def test_edit_member_scoped_to_exploitation(client, setup):
    user, _, _ = setup
    other = User.objects.create_user(email="other@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Autre")
    foreign = TeamMember.objects.create(exploitation=other_exp, name="Pas à moi")
    client.force_login(user)
    assert client.get(f"/equipe/{foreign.id}/modifier/").status_code == 404


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


# ── Invitation à ouvrir un espace employé ────────────────────────────────────


@pytest.mark.django_db
def test_invitation_envoyee_et_horodatee(client, setup, mailoutbox):
    user, _expl, member = setup
    client.force_login(user)
    r = client.post(f"/equipe/{member.id}/inviter/")
    assert r.status_code == 302
    member.refresh_from_db()
    assert member.invitation_sent_at is not None
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["aude@ex.com"]
    assert invitations.jeton(member) in mailoutbox[0].body


@pytest.mark.django_db
def test_fiche_membre_propose_l_invitation(client, setup):
    """La carte « Espace employé » suit l'état du membre : inviter → renvoyer → lié."""
    user, _expl, member = setup
    client.force_login(user)
    url = f"/equipe/{member.id}/modifier/"

    html = client.get(url).content.decode()
    assert "Inviter par email" in html
    assert f"/equipe/{member.id}/inviter/" in html

    client.post(f"/equipe/{member.id}/inviter/")
    assert "Renvoyer l'invitation" in client.get(url).content.decode()

    member.refresh_from_db()
    member.user = User.objects.create_user(email="lie@ex.com", password="pwd12345")
    member.save(update_fields=["user"])
    html = client.get(url).content.decode()
    assert "Compte actif" in html
    assert "Inviter par email" not in html


@pytest.mark.django_db
def test_invitation_refusee_sans_email(client, setup):
    user, exploitation, _m = setup
    sans_email = TeamMember.objects.create(exploitation=exploitation, name="Sans mail")
    client.force_login(user)
    client.post(f"/equipe/{sans_email.id}/inviter/")
    sans_email.refresh_from_db()
    assert sans_email.invitation_sent_at is None


@pytest.mark.django_db
def test_invitation_scoped_to_exploitation(client, setup, mailoutbox):
    """Un autre exploitant ne peut pas inviter les membres d'une équipe voisine."""
    _user, _expl, member = setup
    intrus = User.objects.create_user(email="intrus@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=intrus, name="Ferme voisine")
    client.force_login(intrus)
    assert client.post(f"/equipe/{member.id}/inviter/").status_code == 404
    assert mailoutbox == []


@pytest.mark.django_db
def test_acceptation_cree_le_compte_et_ouvre_l_espace(client, setup):
    _user, _expl, member = setup
    url = f"/equipe/invitation/{invitations.jeton(member)}/"
    assert client.get(url).status_code == 200

    r = client.post(url, {"first_name": "Aude", "last_name": "Martin",
                          "password1": "Tr0ubadour!42", "password2": "Tr0ubadour!42"})
    assert r.status_code == 302
    member.refresh_from_db()
    assert member.user is not None
    assert member.user.email == "aude@ex.com"
    assert member.invitation_accepted_at is not None
    # L'espace employé est ouvert et actif, pas seulement disponible.
    assert client.session["espace"] == "employe"


@pytest.mark.django_db
def test_acceptation_par_un_compte_connecte(client, setup):
    _user, _expl, member = setup
    autre = User.objects.create_user(email="aude@ex.com", password="pwd12345")
    client.force_login(autre)
    r = client.post(f"/equipe/invitation/{invitations.jeton(member)}/")
    assert r.status_code == 302
    member.refresh_from_db()
    assert member.user == autre


@pytest.mark.django_db
def test_jeton_perime_si_l_email_change(setup):
    """Le lien visait une personne : le réattribuer serait une fuite d'accès."""
    _user, _expl, member = setup
    token = invitations.jeton(member)
    assert invitations.membre_du_jeton(token) == member
    member.email = "quelquun.dautre@ex.com"
    member.save(update_fields=["email"])
    assert invitations.membre_du_jeton(token) is None


@pytest.mark.django_db
def test_jeton_bidon_repond_410(client, setup):
    assert client.get("/equipe/invitation/nimportequoi/").status_code == 410


@pytest.mark.django_db
def test_invitation_deja_utilisee(client, setup):
    _user, _expl, member = setup
    token = invitations.jeton(member)
    member.user = User.objects.create_user(email="deja@ex.com", password="pwd12345")
    member.save(update_fields=["user"])
    assert client.get(f"/equipe/invitation/{token}/").status_code == 410
