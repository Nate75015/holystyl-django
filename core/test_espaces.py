"""Résolution des espaces (chef d'entreprise, employé, bailleur, comptable, client)."""
import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

from core import espaces as E
from core.middleware import CurrentExploitationMiddleware
from exploitations.models import Exploitation
from equipe.models import TeamMember
from client.models import Client, Partenaire

U = get_user_model()


def _req(user):
    r = RequestFactory().get("/")
    SessionMiddleware(lambda req: None).process_request(r)
    r.user = user
    return r


def _apply(user):
    r = _req(user)
    CurrentExploitationMiddleware(lambda req: None)(r)
    return r


@pytest.fixture
def expl(db):
    owner = U.objects.create_user(email="chef@x.fr", password="x")
    return Exploitation.objects.create(owner=owner, name="Ferme A")


def test_owner_inchange(expl):
    """Non-régression : le propriétaire retrouve son exploitation."""
    r = _apply(expl.owner)
    assert r.espace == E.EXPLOITANT
    assert r.exploitation.pk == expl.pk


def test_employe(expl):
    u = U.objects.create_user(email="ouvrier@x.fr", password="x")
    TeamMember.objects.create(exploitation=expl, user=u, name="Ouvrier")
    r = _apply(u)
    assert r.espace == E.EMPLOYE
    assert r.exploitation.pk == expl.pk       # avant : None


def test_bailleur(expl):
    u = U.objects.create_user(email="bail@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="SCI",
                              type_partenaire=Partenaire.Type.BAILLEUR)
    r = _apply(u)
    assert r.espace == E.BAILLEUR
    assert r.exploitation.pk == expl.pk       # avant : None


def test_comptable_a_son_espace(expl):
    """Le comptable rattaché à l'exploitation y accède, comme le bailleur."""
    u = U.objects.create_user(email="compta@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="Cabinet",
                              type_partenaire=Partenaire.Type.COMPTABLE)
    r = _apply(u)
    assert r.espace == E.COMPTABLE
    assert r.exploitation.pk == expl.pk


def test_partenaire_sans_type_reconnu_na_pas_despace(expl):
    u = U.objects.create_user(email="avocat@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="Cabinet",
                              type_partenaire=Partenaire.Type.AVOCAT)
    r = _apply(u)
    assert r.espace is None and r.exploitation is None


def test_client_rattache_a_un_compte_a_son_espace(expl):
    u = U.objects.create_user(email="acheteur@x.fr", password="x")
    Client.objects.create(exploitation=expl, user=u, nom="Tricatel")
    r = _apply(u)
    assert r.espace == E.CLIENT
    assert r.exploitation.pk == expl.pk


def test_fiche_client_sans_compte_nouvre_aucun_espace(expl):
    """Une fiche ordinaire, tenue par l'exploitation, n'est pas un compte."""
    Client.objects.create(exploitation=expl, nom="Sans compte")
    u = U.objects.create_user(email="passant@x.fr", password="x")
    assert E.espaces_de(u) == []


def test_lespace_client_est_ferme_les_autres_non():
    assert E.est_ferme(E.CLIENT) is True
    assert E.est_ferme(E.COMPTABLE) is False
    assert E.est_ferme(E.EXPLOITANT) is False


def test_employe_inactif_exclu(expl):
    u = U.objects.create_user(email="parti@x.fr", password="x")
    TeamMember.objects.create(exploitation=expl, user=u, name="Parti", is_active=False)
    assert E.espaces_de(u) == []


def test_sans_rattachement(db):
    u = U.objects.create_user(email="neuf@x.fr", password="x")
    r = _apply(u)
    assert r.espace is None and r.exploitation is None


def test_multi_espaces_et_bascule(expl):
    """Un associé salarié de sa propre exploitation relève des deux espaces."""
    TeamMember.objects.create(exploitation=expl, user=expl.owner, name="Associé")
    assert E.espaces_de(expl.owner) == [E.EXPLOITANT, E.EMPLOYE]

    r = _req(expl.owner)
    assert E.espace_courant(r) == E.EXPLOITANT          # défaut = 1er disponible
    assert E.definir_espace(r, E.EMPLOYE) is True
    assert E.espace_courant(r) == E.EMPLOYE             # mémorisé en session
    assert E.definir_espace(r, E.BAILLEUR) is False     # pas le droit
    assert E.espace_courant(r) == E.EMPLOYE


def test_espace_memorise_devenu_invalide(expl):
    """Un espace perdu entre-temps ne doit pas bloquer l'utilisateur."""
    r = _req(expl.owner)
    r.session[E.SESSION_KEY] = E.BAILLEUR
    assert E.espace_courant(r) == E.EXPLOITANT


# ── Cloisonnement de l'espace client ────────────────────────────────
#
# Le client est le seul titulaire externe à l'exploitation : masquer les
# entrées de navigation ne suffit pas, il faut refuser les URL.


@pytest.fixture
def compte_client(expl):
    u = U.objects.create_user(email="acheteur@x.fr", password="secret123")
    Client.objects.create(exploitation=expl, user=u, nom="Tricatel")
    return u


@pytest.mark.django_db
def test_le_client_atteint_son_espace(client, compte_client):
    client.force_login(compte_client)
    from django.urls import reverse

    assert client.get(reverse("client:espace")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("vue", ["finances:facturation", "finances:charges", "client:clients", "equipe:paie"])
def test_le_client_ne_voit_pas_la_ferme(client, compte_client, vue):
    """Une vue non ouverte à l'espace client est refusée, pas seulement masquée."""
    from django.urls import reverse

    client.force_login(compte_client)
    assert client.get(reverse(vue)).status_code == 403


@pytest.mark.django_db
def test_le_client_garde_la_deconnexion(client, compte_client):
    """Fermer l'espace ne doit pas enfermer son titulaire dedans."""
    from django.urls import reverse

    client.force_login(compte_client)
    assert client.post(reverse("accounts:logout")).status_code in (200, 302)


@pytest.mark.django_db
def test_le_comptable_voit_les_finances_mais_pas_le_reste(client, expl):
    """Espace interne : la nav est filtrée, l'URL reste ouverte (cf. NAV_AUTORISEE)."""
    from django.urls import reverse

    u = U.objects.create_user(email="cabinet@x.fr", password="secret123")
    Partenaire.objects.create(exploitation=expl, user=u, nom="Cabinet",
                              type_partenaire=Partenaire.Type.COMPTABLE)
    client.force_login(u)
    assert client.get(reverse("finances:facturation")).status_code == 200
    autorisees = E.nav_autorisee(E.COMPTABLE)
    assert "finances:bilan_economique" in autorisees
    assert "parcelles:list" not in autorisees
