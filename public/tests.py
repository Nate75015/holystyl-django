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

    page = client.get("/nos-terroirs/").content.decode()
    assert "Ferme Consentante" in page
    assert "Ferme Discrète" not in page and "Forcalquier" not in page
    # L'interrupteur est éteint par défaut : c'est le point.
    assert discrete.annuaire_public is False
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_l_annuaire_est_atteignable_depuis_le_bandeau(client):
    page = client.get("/").content.decode()
    # Barre de navigation, menu compact, et pied de page reste sur l'accueil.
    assert page.count('href="/nos-terroirs/"') >= 2
    assert "Nos terroirs" in page
    assert client.get("/nos-terroirs/").status_code == 200


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

    reponse = client.get("/nos-terroirs/")
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
    reponse = client.get("/nos-terroirs/")
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
    page = client.get("/nos-terroirs/").content.decode()
    assert "nt-photo-vide" in page and ">Z<" in page


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

    lue = client.get("/nos-terroirs/").context["fermes"][0]
    assert lue.ville == "Montpellier" and lue.cp == "34090"
    assert (lue.dep_code, lue.dep_nom, lue.region) == ("34", "Hérault", "Occitanie")


@pytest.mark.django_db
def test_sans_adresse_l_annuaire_retombe_sur_l_exploitation(client, django_user_model):
    """Le miroir reste le repli : une ferme sans adresse n'est pas perdue."""
    from exploitations.models import Exploitation

    u = django_user_model.objects.create_user(email="repli@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=u, name="Ferme Repli", city="Quimper",
                                postal_code="29000", annuaire_public=True)

    lue = client.get("/nos-terroirs/").context["fermes"][0]
    assert lue.ville == "Quimper" and lue.dep_nom == "Finistère"


@pytest.mark.django_db
def test_le_bandeau_de_marque_reste_lisible(client):
    """Le jaune ne sert jamais de texte sur fond clair, et le titre est explicite.

    Le titre héritait du bandeau noir, mais une règle globale sur `h1` impose
    la couleur de texte de l'application : il ressortait noir sur noir.
    """
    page = client.get("/nos-terroirs/").content.decode()
    assert "Nos <em>terroirs</em>" in page and "by Isidor" in page
    assert ".nt-marque {" in page and "color: #FFFFFF;" in page
    # La pastille jaune porte du texte noir, jamais l'inverse.
    assert "background: var(--nt-jaune); color: var(--nt-noir);" in page
    assert "0 %" in page and "de commission" in page
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_nos_terroirs_a_son_propre_bandeau_jaune(client):
    """La place de marché porte sa marque, pas celle du produit.

    Elle garde les commandes qui servent partout — langue, thème, connexion,
    inscription — mais abandonne le bandeau turquoise du reste de la vitrine.
    """
    page = client.get("/nos-terroirs/").content.decode()
    assert 'class="nt-bandeau"' in page
    assert 'class="lp-header"' not in page, "l'ancien bandeau est encore là"
    assert "background: var(--nt-jaune); color: var(--nt-noir);" in page

    # Les commandes conservées : langue, thème, connexion, inscription.
    for attendu in ("Connexion", "S'inscrire", "django_language", 'id="nt-geo"'):
        assert attendu in page, attendu

    # La goutte ramène à l'accueil du produit.
    assert 'class="nt-goutte"' in page and 'href="/"' in page
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_la_bascule_de_theme_prend_la_couleur_de_son_bandeau(client):
    """Un seul composant pour deux bandeaux : turquoise à texte clair, jaune à
    texte noir. Un jeton fixe l'aurait rendu illisible sur l'un des deux."""
    for url in ("/", "/nos-terroirs/"):
        page = client.get(url).content.decode()
        assert "color-mix(in srgb, currentColor 90%, transparent)" in page, url
        assert "var(--on-action) 90%" not in page, url


@pytest.mark.django_db
def test_la_grille_des_producteurs_prend_toute_la_largeur(client):
    """Pleine largeur, mais sans jamais déborder sur un écran étroit.

    `auto-fill` ajoute des colonnes au lieu d'étirer les fiches ; le
    `min(288px, 100%)` empêche la piste de rester à 288 px sur un écran de
    320, ce qui pousserait la page hors de l'écran.
    """
    page = client.get("/nos-terroirs/").content.decode()
    assert "repeat(auto-fill, minmax(min(288px, 100%), 1fr))" in page
    # Plus de conteneur borné sur le corps ni sur le bandeau.
    assert ".nt-corps { padding:" in page
    assert "max-width: var(--nt-max); margin-inline: auto" not in page
    # Les filtres, eux, restent saisissables.
    assert "max-width: 1180px;" in page


@pytest.mark.django_db
def test_la_grille_respire_sous_les_filtres(client):
    """Elle suit toujours quelque chose : une recherche, des filtres, un titre.

    Sans marge par défaut elle s'y colle — c'est arrivé en mutualisant la
    règle, qui avait perdu son `margin-top` au passage.
    """
    page = client.get("/nos-terroirs/").content.decode()
    assert "margin-top: clamp(28px, 3.5vw, 44px);" in page
    # La page ne remet pas la grille à zéro par un style en ligne.
    assert 'class="nt-grille" style="margin-top: 0' not in page


@pytest.mark.django_db
def test_le_pied_de_page_ferme_les_pages_du_marche(client):
    """Il rappelle la promesse et rouvre les deux chemins : acheter, produire."""
    for url in ("/nos-terroirs/", "/marche/"):
        page = client.get(url).content.decode()
        assert 'class="nt-pied"' in page, url
        assert "0 %" in page and "de commission" in page, url
        # Les deux publics : le marché pour qui achète, Isidor pour qui produit.
        for lien in ('href="/marche/"', 'href="/emplois/"', 'href="/"'):
            assert lien in page, f"{url} : {lien}"
        assert "{#" not in page and "{{" not in page, url


@pytest.mark.django_db
def test_le_bandeau_du_marche_porte_la_goutte(client):
    """La marque du marché s'écrit avec le logo, comme celle du produit."""
    import re

    for url in ("/nos-terroirs/", "/marche/"):
        corps = client.get(url).content.decode()
        m = re.search(r'<div class="nt-wordmark">.*?</div>', corps, re.S)
        assert m, f"pas de marque sur {url}"
        marque = m.group(0)
        # La goutte ramène au produit, le nom à la vitrine du marché.
        assert re.search(r'<a href="/" class="nt-goutte-lien".*?<svg', marque, re.S), url
        assert 'href="/nos-terroirs/" class="nt-wordmark-texte"' in marque, url
        assert "Nos terroirs" in marque and "by Isidor" in marque

    # Les pages Isidor gardent leur propre bandeau.
    assert 'class="nt-wordmark"' not in client.get("/emplois/").content.decode()


@pytest.mark.django_db
def test_l_ananas_est_decoratif_et_se_tait_si_on_le_demande(client):
    """Un ornement ne doit ni parler aux lecteurs d'écran ni imposer son mouvement."""
    page = client.get("/nos-terroirs/").content.decode()
    assert 'id="nt-ananas"' in page and 'aria-hidden="true"' in page
    # Le mouvement se coupe des deux côtés : en CSS et dans le script.
    assert "@media (prefers-reduced-motion: reduce)" in page
    assert "matchMedia('(prefers-reduced-motion: reduce)')" in page
    assert "if (doux.matches) return;" in page
    # Trois plans à des profondeurs distinctes : c'est ce qui fait le volume.
    assert "transform-style: preserve-3d" in page
    assert "translateZ(-70px)" in page and "translateZ(48px)" in page


@pytest.mark.django_db
def test_l_accueil_defend_la_souverainete_numerique(client):
    """La promesse de données n'est pas qu'une case à cocher : elle a sa bande."""
    page = client.get("/").content.decode()
    assert "souveraineté alimentaire" in page and "souveraineté numérique" in page
    assert "Hébergement en France" in page and "Jamais revendues" in page
    # Couleur explicite : une règle globale sur les titres bat l'héritage, et
    # la question ressortait sombre sur sombre.
    assert ".lp-souv-q {\n    color: var(--page);" in page


@pytest.mark.django_db
def test_l_accueil_occupe_toute_la_largeur(client):
    """Pleine largeur pour les grilles, lignes bornées pour le texte."""
    page = client.get("/").content.decode()
    assert ".lp-wrap { padding-inline: var(--lp-gutter); }" in page
    # Ni le conteneur ni le bandeau ne sont plus bornés — sinon la marque
    # resterait en retrait pendant que les sections partent au bord.
    assert "--lp-max" not in page
    # Le héros garde une colonne lisible malgré la largeur disponible.
    assert ".lp-hero-texte { max-width: 40rem; }" in page
