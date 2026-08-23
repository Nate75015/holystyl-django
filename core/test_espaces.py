"""Résolution des espaces (chef d'entreprise, employé, bailleur)."""
import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

from core import espaces as E
from core.middleware import CurrentExploitationMiddleware
from exploitations.models import Exploitation
from equipe.models import TeamMember
from client.models import Partenaire

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


def test_partenaire_non_bailleur_na_pas_despace(expl):
    u = U.objects.create_user(email="compta@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="Cabinet",
                              type_partenaire=Partenaire.Type.COMPTABLE)
    r = _apply(u)
    assert r.espace is None and r.exploitation is None


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
