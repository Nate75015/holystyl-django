"""Les trois tableaux de bord et l'aiguillage `core:dashboard`."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from client.models import Partenaire
from contrat.models import Bail
from equipe.models import Task, TeamMember
from exploitations.models import Exploitation

U = get_user_model()


@pytest.fixture
def expl(db):
    owner = U.objects.create_user(email="chef@x.fr", password="x")
    return Exploitation.objects.create(owner=owner, name="Ferme A")


def _log(client, user):
    client.force_login(user)
    return client


def test_exploitant_rend(client, expl):
    r = _log(client, expl.owner).get(reverse("dashboard:exploitant"))
    assert r.status_code == 200
    assert "Ferme A" in r.content.decode()


def test_alias_core_dashboard_aiguille(client, expl):
    """L'ancienne URL /pulse/ ne doit pas casser."""
    r = _log(client, expl.owner).get(reverse("core:dashboard"))
    assert r.status_code == 302
    assert r.url == reverse("dashboard:exploitant")


def test_employe_voit_ses_taches(client, expl):
    u = U.objects.create_user(email="ouvrier@x.fr", password="x")
    m = TeamMember.objects.create(exploitation=expl, user=u, name="Zoé")
    Task.objects.create(exploitation=expl, title="Tailler la vigne", assigned_to=m)
    Task.objects.create(exploitation=expl, title="Déjà faite", assigned_to=m,
                        status=Task.Status.DONE)

    r = _log(client, u).get(reverse("core:dashboard"))
    assert r.url == reverse("dashboard:employe")        # aiguillé selon l'espace

    html = _log(client, u).get(reverse("dashboard:employe")).content.decode()
    assert "Tailler la vigne" in html
    assert "Déjà faite" not in html                     # terminée : exclue


def test_bailleur_voit_ses_baux(client, expl):
    u = U.objects.create_user(email="bail@x.fr", password="x")
    p = Partenaire.objects.create(exploitation=expl, user=u, nom="SCI Dupont",
                                  type_partenaire=Partenaire.Type.BAILLEUR)
    Bail.objects.create(exploitation=expl, designation="Parcelle Nord",
                        partenaire=p, surface_ha=12.5, loyer_annuel=1800)
    autre = Partenaire.objects.create(exploitation=expl, nom="SCI Martin",
                                      type_partenaire=Partenaire.Type.BAILLEUR)
    Bail.objects.create(exploitation=expl, designation="Parcelle Sud", partenaire=autre)

    r = _log(client, u).get(reverse("core:dashboard"))
    assert r.url == reverse("dashboard:bailleur")

    html = _log(client, u).get(reverse("dashboard:bailleur")).content.decode()
    assert "Parcelle Nord" in html
    assert "Parcelle Sud" not in html                   # bail d'un autre bailleur
    assert "12,5" in html and "1800,0" in html          # totaux (locale fr)


def test_bail_non_rattache_invisible(client, expl):
    """Un bail dont le champ texte `bailleur` porte le nom ne suffit pas."""
    u = U.objects.create_user(email="bail2@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="SCI Dupont",
                              type_partenaire=Partenaire.Type.BAILLEUR)
    Bail.objects.create(exploitation=expl, designation="Vieux bail", bailleur="SCI Dupont")

    html = _log(client, u).get(reverse("dashboard:bailleur")).content.decode()
    assert "Vieux bail" not in html


def test_sans_espace_tombe_sur_exploitant(client, db):
    u = U.objects.create_user(email="neuf@x.fr", password="x")
    r = _log(client, u).get(reverse("core:dashboard"))
    assert r.url == reverse("dashboard:exploitant")
    html = _log(client, u).get(reverse("dashboard:exploitant")).content.decode()
    assert "Configurer mon exploitation" in html        # onboarding


# ── Nav filtrée par espace + bascule ────────────────────────────────────


def test_nav_employe_restreinte(client, expl):
    u = U.objects.create_user(email="ouv2@x.fr", password="x")
    TeamMember.objects.create(exploitation=expl, user=u, name="Zoé")
    html = _log(client, u).get(reverse("dashboard:employe")).content.decode()
    assert "Tâches" in html and "Planning" in html
    for interdit in ("Paie", "Contrats de travail", "Aquaculture", "Patrimoine"):
        assert interdit not in html


def test_nav_bailleur_restreinte(client, expl):
    u = U.objects.create_user(email="bail3@x.fr", password="x")
    Partenaire.objects.create(exploitation=expl, user=u, nom="SCI",
                              type_partenaire=Partenaire.Type.BAILLEUR)
    html = _log(client, u).get(reverse("dashboard:bailleur")).content.decode()
    assert "Baux" in html
    for interdit in ("Paie", "Clients", "Aquaculture", "Sociétés liées"):
        assert interdit not in html


def test_nav_exploitant_complete(client, expl):
    """Non-régression : le chef d'entreprise garde toute la nav."""
    html = _log(client, expl.owner).get(reverse("dashboard:exploitant")).content.decode()
    for attendu in ("Paie", "Aquaculture", "Patrimoine", "Clients"):
        assert attendu in html


def test_selecteur_masque_si_un_seul_espace(client, expl):
    html = _log(client, expl.owner).get(reverse("dashboard:exploitant")).content.decode()
    assert reverse("dashboard:basculer") not in html


def test_bascule(client, expl):
    """Un associé salarié bascule entre ses deux espaces."""
    TeamMember.objects.create(exploitation=expl, user=expl.owner, name="Associé")
    c = _log(client, expl.owner)

    html = c.get(reverse("dashboard:exploitant")).content.decode()
    assert reverse("dashboard:basculer") in html        # sélecteur affiché

    r = c.post(reverse("dashboard:basculer"), {"espace": "employe"})
    assert r.status_code == 302
    assert c.get(reverse("core:dashboard")).url == reverse("dashboard:employe")


def test_bascule_vers_espace_interdit_ignoree(client, expl):
    c = _log(client, expl.owner)
    c.post(reverse("dashboard:basculer"), {"espace": "bailleur"})
    assert c.get(reverse("core:dashboard")).url == reverse("dashboard:exploitant")


def test_bascule_refuse_le_get(client, expl):
    r = _log(client, expl.owner).get(reverse("dashboard:basculer"))
    assert r.status_code == 405
