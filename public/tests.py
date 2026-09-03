"""Tests public : landing, lead magnet, Alex, activation."""

import json

import pytest
from django.contrib.auth import get_user_model

from public.models import LeadCapture
from public import services

User = get_user_model()


@pytest.mark.django_db
def test_home_public_then_redirect_when_authenticated(client):
    assert client.get("/").status_code == 200  # anonyme : landing
    user = User.objects.create_user(email="h@ex.com", password="pwd12345")
    client.force_login(user)
    resp = client.get("/")
    assert resp.status_code == 302 and "/pulse/" in resp.url


@pytest.mark.django_db
def test_lead_capture(client):
    resp = client.post("/lead/", {"email": "prospect@ex.com"})
    assert resp.status_code == 302
    assert LeadCapture.objects.filter(email="prospect@ex.com").exists()


@pytest.mark.django_db
def test_alex_not_configured(client, monkeypatch):
    monkeypatch.setattr(services.llm, "is_configured", lambda: False)
    resp = client.post("/alex/", data=json.dumps({"messages": [{"role": "user", "content": "Bonjour"}]}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert "Alex" in resp.json()["response"]


@pytest.mark.django_db
def test_alex_configured_mocked(client, monkeypatch):
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(services.llm, "generate_text", lambda msgs, **k: "Ravi de vous aider !")
    resp = client.post("/alex/", data=json.dumps({"messages": [{"role": "user", "content": "C'est quoi le DTI ?"}]}),
                       content_type="application/json")
    assert resp.json()["response"] == "Ravi de vous aider !"


@pytest.mark.django_db
def test_la_bascule_jour_nuit_est_sur_les_pages_publiques(client):
    """Un visiteur non connecté n'a ni barre d'application ni menu avatar.

    La bascule de thème n'existait qu'à ces deux endroits : sans elle, le mode
    nuit était injoignable depuis la vitrine.
    """
    for url in ("/", "/emplois/", "/marche/"):
        page = client.get(url).content.decode()
        assert 'x-show="dark"' in page, f"{url} : pas de bascule de thème"
        assert "toggle()" in page, f"{url} : la bascule n'appelle rien"
        # Le bandeau est teinté : ses commandes doivent dériver de `--on-action`,
        # sinon le mode nuit y écrit du blanc sur un cyan clair.
        assert "text-white/" not in page, f"{url} : blanc codé en dur dans l'entête"
        assert "{#" not in page and "{{" not in page, f"{url} : gabarit mal rendu"


@pytest.mark.django_db
def test_la_page_reste_lisible_sans_javascript(client):
    """Le masquage des blocs est conditionné à `.lp-js`.

    Une page de vente ne peut pas dépendre d'une animation pour être lisible :
    sans JavaScript, aucun bloc ne doit être masqué.
    """
    page = client.get("/").content.decode()
    assert ".lp-js .lp-reveal { opacity: 0" in page
    assert "classList.add('lp-js')" in page
    # Aucune règle ne masque un bloc en dehors de ce garde-fou.
    assert ".lp-reveal { opacity: 0" not in page.replace(".lp-js .lp-reveal { opacity: 0", "")


@pytest.mark.django_db
def test_le_tarif_affiche_la_part_fixe_et_la_part_a_l_hectare(client):
    """19,90 € par exploitation, plus 0,70 € par hectare et par mois."""
    page = client.get("/").content.decode()
    assert "59,90" not in page, "ancien tarif encore affiché"
    assert "19,90€" in page and "0,70 €" in page
    # Le total se calcule côté page : sans le curseur, la part variable est
    # invisible et le tarif devient incompréhensible.
    assert 'id="lp-ha"' in page and "19.9 + 0.7 * this.ha" in page


@pytest.mark.django_db
def test_les_douze_domaines_sont_annonces_et_la_grille_est_pleine(client):
    """La grille bento alterne 2 grandes (3 colonnes) et 3 moyennes (2).

    Douze cellules font 30 colonnes, soit cinq rangées pleines : une cellule
    de plus ou de moins laisserait un trou en bout de rangée.
    """
    import re

    page = client.get("/").content.decode()
    assert "Douze domaines" in page and "Dix domaines" not in page
    assert "Facture électronique" in page and "Signature électronique" in page

    cellules = re.findall(r'<div class="lp-cell( lp-cell-lg)?">', page)
    assert len(cellules) == 12
    colonnes = sum(3 if grande else 2 for grande in cellules)
    assert colonnes % 6 == 0, f"{colonnes} colonnes : la dernière rangée serait incomplète"


@pytest.mark.django_db
def test_le_bandeau_mene_aux_offres_d_emploi(client):
    """Le seul lien du bandeau qui quitte la page d'accueil."""
    page = client.get("/").content.decode()
    # Barre de navigation, menu compact sous le seuil, et pied de page.
    assert page.count('href="/emplois/"') == 3
    assert "Offres d'emploi" in page
    # La cible existe et s'ouvre sans compte.
    assert client.get("/emplois/").status_code == 200


@pytest.mark.django_db
def test_l_annuaire_ne_publie_que_les_fermes_consentantes(client, django_user_model):
    """Le nom et la commune d'un exploitant ne se publient pas sans son accord."""
    from exploitations.models import Exploitation

    u1 = django_user_model.objects.create_user(email="ok@ex.com", password="pwd12345")
    u2 = django_user_model.objects.create_user(email="non@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=u1, name="Ferme Consentante",
                                city="Manosque", annuaire_public=True)
    discrete = Exploitation.objects.create(owner=u2, name="Ferme Discrète", city="Forcalquier")

    page = client.get("/exploitants/").content.decode()
    assert "Ferme Consentante" in page
    assert "Ferme Discrète" not in page and "Forcalquier" not in page
    # L'interrupteur est éteint par défaut : c'est le point.
    assert discrete.annuaire_public is False
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_l_annuaire_est_atteignable_depuis_le_bandeau(client):
    page = client.get("/").content.decode()
    # Barre de navigation, menu compact, et pied de page reste sur l'accueil.
    assert page.count('href="/exploitants/"') >= 2
    assert "Exploitants agricoles" in page
    assert client.get("/exploitants/").status_code == 200


@pytest.mark.django_db
def test_l_annuaire_se_filtre_sur_la_geographie(client, django_user_model):
    """Région, département et ville se déduisent du code postal, jamais saisis."""
    from exploitations.models import Exploitation

    for i, (nom, ville, cp) in enumerate([
        ("Ferme Sud", "Manosque", "04100"),
        ("Ferme Ouest", "Quimper", "29000"),
        ("Ferme Sans Code", "Nulle Part", ""),
    ]):
        u = django_user_model.objects.create_user(email=f"geo{i}@ex.com", password="pwd12345")
        Exploitation.objects.create(owner=u, name=nom, city=ville,
                                    postal_code=cp, annuaire_public=True)

    reponse = client.get("/exploitants/")
    situees = {f.name: (f.region, f.dep_code, f.dep_nom) for f in reponse.context["fermes"]}
    assert situees["Ferme Sud"] == ("Provence-Alpes-Côte d'Azur", "04", "Alpes-de-Haute-Provence")
    assert situees["Ferme Ouest"] == ("Bretagne", "29", "Finistère")
    # Sans code postal, la ferme reste listée mais sans géographie inventée.
    assert situees["Ferme Sans Code"] == (None, None, None)

    page = reponse.content.decode()
    assert 'data-dep="04"' in page and 'data-region="Bretagne"' in page
    assert "data-texte=" in page and "Finistère" in page
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_les_listes_offrent_toute_la_france(client):
    """Les menus ne se limitent pas aux fermes présentes.

    Un visiteur doit pouvoir chercher dans une région même vide : la liste
    vient du référentiel, pas des données.
    """
    reponse = client.get("/exploitants/")
    referentiel = reponse.context["referentiel"]
    assert len(referentiel) == 18
    assert sum(len(r["departements"]) for r in referentiel) == 101

    # Régions triées accents ignorés : « Île-de-France » se classe à I.
    noms = [r["region"] for r in referentiel]
    assert noms.index("Hauts-de-France") < noms.index("Île-de-France") < noms.index("Normandie")

    # Ordre administratif : la Corse s'intercale entre le 19 et le 21.
    codes = [d["code"] for r in referentiel for d in r["departements"]]
    corse = next(r for r in referentiel if r["region"] == "Corse")
    assert [d["code"] for d in corse["departements"]] == ["2A", "2B"]
    assert "971" in codes and "01" in codes


@pytest.mark.django_db
def test_la_photo_de_ferme_a_une_place_de_repli(client, django_user_model):
    """Sans photo, une plaque à l'initiale — jamais un cadre vide."""
    from exploitations.models import Exploitation

    u = django_user_model.objects.create_user(email="photo@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=u, name="Zephyr", annuaire_public=True)
    page = client.get("/exploitants/").content.decode()
    assert "lp-photo-vide" in page and ">Z<" in page


@pytest.mark.django_db
def test_l_annuaire_lit_l_adresse_principale_et_non_le_miroir(client, django_user_model):
    """Les champs de l'exploitation ne sont qu'un miroir, et il peut diverger.

    Cas réel rencontré : `Exploitation.city` disait « Digne-les-Bains » sans
    code postal, alors que l'adresse enregistrée était à Montpellier. Filtrer
    sur PACA ne trouvait rien, et c'était juste — mais la fiche mentait.
    """
    from exploitations.models import AdresseExploitation, Exploitation

    u = django_user_model.objects.create_user(email="miroir@ex.com", password="pwd12345")
    ferme = Exploitation.objects.create(
        owner=u, name="Ferme Miroir", city="Digne-les-Bains", postal_code="",
        annuaire_public=True)
    AdresseExploitation.objects.create(
        exploitation=ferme, city="Montpellier", postal_code="34090", principale=True)

    lue = client.get("/exploitants/").context["fermes"][0]
    assert lue.ville == "Montpellier" and lue.cp == "34090"
    assert (lue.dep_code, lue.dep_nom, lue.region) == ("34", "Hérault", "Occitanie")


@pytest.mark.django_db
def test_sans_adresse_l_annuaire_retombe_sur_l_exploitation(client, django_user_model):
    """Le miroir reste le repli : une ferme sans adresse n'est pas perdue."""
    from exploitations.models import Exploitation

    u = django_user_model.objects.create_user(email="repli@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=u, name="Ferme Repli", city="Quimper",
                                postal_code="29000", annuaire_public=True)

    lue = client.get("/exploitants/").context["fermes"][0]
    assert lue.ville == "Quimper" and lue.dep_nom == "Finistère"
