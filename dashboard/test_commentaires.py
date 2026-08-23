"""Aucun commentaire de template ne doit fuir dans le HTML rendu.

`{# … #}` ne fonctionne que sur une seule ligne en Django : un commentaire
multi-ligne n'est pas reconnu par le lexer et sort tel quel dans la page.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from client.models import Partenaire
from equipe.models import TeamMember
from exploitations.models import Exploitation

U = get_user_model()


@pytest.fixture
def expl(db):
    owner = U.objects.create_user(email="chef@x.fr", password="x")
    return Exploitation.objects.create(owner=owner, name="Ferme A")


def _sans_commentaire(html):
    assert "{#" not in html and "#}" not in html
    assert "{% comment" not in html and "endcomment" not in html


def test_exploitant(client, expl):
    client.force_login(expl.owner)
    _sans_commentaire(client.get(reverse("dashboard:exploitant")).content.decode())


def test_employe(client, expl):
    u = U.objects.create_user(email="o@x.fr", password="x")
    TeamMember.objects.create(exploitation=expl, user=u, name="Zoé")
    client.force_login(u)
    _sans_commentaire(client.get(reverse("dashboard:employe")).content.decode())


def test_employe_sans_rattachement(client, expl):
    """Passe par la branche qui portait le commentaire cassé."""
    u = U.objects.create_user(email="o2@x.fr", password="x")
    m = TeamMember.objects.create(exploitation=expl, user=u, name="Zoé")
    client.force_login(u)
    m.is_active = False
    m.save(update_fields=["is_active"])
    _sans_commentaire(client.get(reverse("dashboard:employe")).content.decode())


def test_bailleur(client, expl):
    u = U.objects.create_user(email="b@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="SCI",
                              type_partenaire=Partenaire.Type.BAILLEUR)
    client.force_login(u)
    _sans_commentaire(client.get(reverse("dashboard:bailleur")).content.decode())


def test_dti_liste(client, expl):
    """Commentaire multi-ligne préexistant, hors de mes modifications."""
    client.force_login(expl.owner)
    _sans_commentaire(client.get(reverse("dti:liste")).content.decode())
