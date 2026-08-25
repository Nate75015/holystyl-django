"""Tests du socle d'authentification (email/mot de passe)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_user_uses_email_as_identifier():
    user = User.objects.create_user(email="agri@example.com", password="pwd12345")
    assert user.email == "agri@example.com"
    assert user.USERNAME_FIELD == "email"
    assert user.check_password("pwd12345")
    assert user.display_name  # dérivé de l'email si pas de nom complet


@pytest.mark.django_db
def test_superuser_flags():
    admin = User.objects.create_superuser(email="boss@example.com", password="pwd12345")
    assert admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    resp = client.get(reverse("core:dashboard"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


@pytest.mark.django_db
def test_login_then_dashboard(client):
    User.objects.create_user(email="demo@example.com", password="pwd12345")
    ok = client.login(email="demo@example.com", password="pwd12345")
    assert ok
    resp = client.get(reverse("core:dashboard"), follow=True)
    assert resp.status_code == 200
    assert b"Holystyl" in resp.content


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    resp = client.post(
        reverse("accounts:register"),
        {
            "first_name": "Jean",
            "last_name": "Nouveau",
            "email": "new@example.com",
            "birth_date": "1985-04-12",
            "address_number": "12",
            "address_street": "rue des Champs",
            "address_zip": "31000",
            "address_city": "Toulouse",
            "password1": "ComplexePwd!2026",
            "password2": "ComplexePwd!2026",
        },
    )
    assert resp.status_code == 302
    user = User.objects.get(email="new@example.com")
    assert user.full_name == "Jean Nouveau"
    assert user.birth_date.isoformat() == "1985-04-12"
    assert user.address_city == "Toulouse"


# ── Première connexion sans invitation ──────────────────────────────
#
# Un compte créé sur invitation arrive rattaché : son espace existe. Sans
# rattachement, on demande le profil au lieu de supposer un chef d'entreprise.

import pytest
from django.urls import reverse

from core import espaces as E
from exploitations.models import Exploitation


@pytest.fixture
def nouveau(db):
    return get_user_model().objects.create_user(email="neuf@test.fr", password="secret123")


@pytest.mark.django_db
def test_premiere_connexion_demande_le_profil(client, nouveau):
    client.force_login(nouveau)
    resp = client.get(reverse("core:dashboard"), follow=True)
    assert resp.redirect_chain[-1][0] == reverse("accounts:choix_profil")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_le_chef_dentreprise_arrive_sur_son_tableau(client, nouveau):
    client.force_login(nouveau)
    resp = client.post(reverse("accounts:choix_profil"), {"profil": E.EXPLOITANT})
    assert resp.url == reverse("dashboard:exploitant")
    nouveau.refresh_from_db()
    assert nouveau.profil_souhaite == E.EXPLOITANT


@pytest.mark.django_db
@pytest.mark.parametrize("profil", [E.EMPLOYE, E.BAILLEUR, E.COMPTABLE])
def test_chaque_profil_arrive_sur_son_tableau_de_bord(client, nouveau, profil):
    """Le tableau s'ouvre même sans rattachement : vide, avec le geste à faire."""
    client.force_login(nouveau)
    resp = client.post(reverse("accounts:choix_profil"), {"profil": profil})
    assert resp.url == reverse(E.tableau_de_bord(profil))

    page = client.get(resp.url)
    assert page.status_code == 200
    contenu = page.content.decode()
    assert "Votre espace n'est pas encore ouvert" in contenu
    assert nouveau.email in contenu          # l'adresse à communiquer


@pytest.mark.django_db
def test_un_profil_declare_nouvre_pas_les_autres_tableaux(client, nouveau):
    """Se dire bailleur n'ouvre pas l'écran des employés."""
    client.force_login(nouveau)
    client.post(reverse("accounts:choix_profil"), {"profil": E.BAILLEUR})
    assert client.get(reverse("dashboard:bailleur")).status_code == 200
    assert client.get(reverse("dashboard:employe")).status_code == 403
    assert client.get(reverse("dashboard:comptable")).status_code == 403


@pytest.mark.django_db
def test_un_profil_inconnu_est_refuse(client, nouveau):
    client.force_login(nouveau)
    client.post(reverse("accounts:choix_profil"), {"profil": "president"})
    nouveau.refresh_from_db()
    assert nouveau.profil_souhaite == ""


@pytest.mark.django_db
def test_le_client_ne_se_declare_pas(client, nouveau):
    """Une fiche client se crée depuis l'exploitation qui facture, pas ici."""
    client.force_login(nouveau)
    client.post(reverse("accounts:choix_profil"), {"profil": E.CLIENT})
    nouveau.refresh_from_db()
    assert nouveau.profil_souhaite == ""


@pytest.mark.django_db
def test_un_compte_rattache_nest_pas_derange(client, nouveau):
    """L'invité, lui, a déjà un espace : la page de choix le renvoie chez lui."""
    Exploitation.objects.create(owner=nouveau, name="Ferme")
    client.force_login(nouveau)
    resp = client.get(reverse("accounts:choix_profil"))
    assert resp.status_code == 302 and resp.url == reverse("core:dashboard")
    resp = client.get(reverse("core:dashboard"), follow=True)
    assert reverse("accounts:choix_profil") not in [u for u, _ in resp.redirect_chain]
