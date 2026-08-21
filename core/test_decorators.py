"""Contrôle d'accès par espace (@espace_requis)."""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from client.models import Partenaire
from core.decorators import espace_requis
from core.espaces import BAILLEUR, EMPLOYE, EXPLOITANT
from equipe.models import TeamMember
from exploitations.models import Exploitation

U = get_user_model()


@pytest.fixture
def expl(db):
    owner = U.objects.create_user(email="chef@x.fr", password="x")
    return Exploitation.objects.create(owner=owner, name="Ferme A")


@pytest.fixture
def employe_user(expl):
    u = U.objects.create_user(email="ouvrier@x.fr", password="x")
    TeamMember.objects.create(exploitation=expl, user=u, name="Zoé")
    return u


@pytest.fixture
def bailleur_user(expl):
    u = U.objects.create_user(email="bail@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="SCI",
                              type_partenaire=Partenaire.Type.BAILLEUR)
    return u


# ── Validation à l'import ───────────────────────────────────────────────


def test_espace_inconnu_casse_au_chargement():
    with pytest.raises(ValueError, match="inconnu"):
        espace_requis("chef_dentreprise")      # faute de frappe


def test_aucun_espace_refuse():
    with pytest.raises(ValueError):
        espace_requis()


# ── Refus effectif ──────────────────────────────────────────────────────


def test_employe_bloque_sur_la_paie(client, employe_user):
    """Le nerf de l'affaire : la nav masquait la paie, l'URL restait tapable."""
    client.force_login(employe_user)
    assert client.get(reverse("equipe:paie")).status_code == 403
    assert client.get(reverse("equipe:contrats")).status_code == 403
    assert client.get(reverse("equipe:equipe")).status_code == 403


def test_bailleur_bloque_sur_la_paie(client, bailleur_user):
    client.force_login(bailleur_user)
    assert client.get(reverse("equipe:paie")).status_code == 403


def test_exploitant_passe(client, expl):
    client.force_login(expl.owner)
    assert client.get(reverse("equipe:paie")).status_code == 200


def test_message_nomme_lespace_requis(client, employe_user):
    client.force_login(employe_user)
    html = client.get(reverse("equipe:paie")).content.decode()
    # L'apostrophe est échappée par l'autoescape : on vise le texte autour.
    assert "Cette page appartient" in html and "Chef d" in html and "entreprise" in html


# ── Cloisonnement des tableaux de bord ──────────────────────────────────


def test_dashboards_cloisonnes(client, expl, employe_user, bailleur_user):
    cas = [
        (expl.owner, "dashboard:exploitant", 200),
        (expl.owner, "dashboard:employe", 403),
        (expl.owner, "dashboard:bailleur", 403),
        (employe_user, "dashboard:employe", 200),
        (employe_user, "dashboard:exploitant", 403),
        (bailleur_user, "dashboard:bailleur", 200),
        (bailleur_user, "dashboard:exploitant", 403),
    ]
    for user, vue, attendu in cas:
        client.force_login(user)
        assert client.get(reverse(vue)).status_code == attendu, (user.email, vue)


# ── Cas limites ─────────────────────────────────────────────────────────


def test_onboarding_reste_accessible(client, db):
    """Sans rattachement, l'écran exploitant doit rester ouvert (sans_espace)."""
    u = U.objects.create_user(email="neuf@x.fr", password="x")
    client.force_login(u)
    resp = client.get(reverse("dashboard:exploitant"))
    assert resp.status_code == 200
    assert b"Configurer mon exploitation" in resp.content


def test_sans_espace_bloque_ailleurs(client, db):
    u = U.objects.create_user(email="neuf2@x.fr", password="x")
    client.force_login(u)
    assert client.get(reverse("dashboard:employe")).status_code == 403


def test_anonyme_renvoye_vers_la_connexion(client, db):
    """Un visiteur non connecté a droit à la page de login, pas à un 403."""
    resp = client.get(reverse("equipe:paie"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url or "login" in resp.url


def test_le_controle_porte_sur_lespace_actif(client, expl):
    """Un associé salarié perd l'accès RH tant qu'il est en espace employé."""
    TeamMember.objects.create(exploitation=expl, user=expl.owner, name="Associé")
    client.force_login(expl.owner)
    assert client.get(reverse("equipe:paie")).status_code == 200

    client.post(reverse("dashboard:basculer"), {"espace": "employe"})
    assert client.get(reverse("equipe:paie")).status_code == 403

    client.post(reverse("dashboard:basculer"), {"espace": "exploitant"})
    assert client.get(reverse("equipe:paie")).status_code == 200
