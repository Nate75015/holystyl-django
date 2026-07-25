"""Tests parcelles : CRUD web + API + isolation multi-tenant."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from exploitations.models import Exploitation
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def user_exploitation(db):
    user = User.objects.create_user(email="a@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme A", total_area=10)
    return user, exploitation


@pytest.mark.django_db
def test_create_parcelle_web(client, user_exploitation):
    user, exploitation = user_exploitation
    client.force_login(user)
    resp = client.post(
        reverse("parcelles:create"),
        {"name": "Nord", "area": 2.5, "kc_value": 1.0, "status": "active"},
    )
    assert resp.status_code == 302
    parcelle = Parcelle.objects.get(name="Nord")
    assert parcelle.exploitation == exploitation


@pytest.mark.django_db
def test_create_requires_onboarding(client):
    user = User.objects.create_user(email="b@ex.com", password="pwd12345")
    client.force_login(user)
    resp = client.get(reverse("parcelles:create"))
    assert resp.status_code == 302
    assert reverse("exploitations:settings") in resp.url


@pytest.mark.django_db
def test_api_list_is_tenant_scoped(client, user_exploitation):
    user, exploitation = user_exploitation
    Parcelle.objects.create(exploitation=exploitation, name="P1")
    # Autre utilisateur / autre exploitation
    other = User.objects.create_user(email="c@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Ferme C")
    Parcelle.objects.create(exploitation=other_exp, name="P2")

    client.force_login(user)
    resp = client.get("/api/parcelles/")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"P1"}  # P2 (autre tenant) absente


@pytest.mark.django_db
def test_api_create_attaches_exploitation(client, user_exploitation):
    user, exploitation = user_exploitation
    client.force_login(user)
    resp = client.post("/api/parcelles/", {"name": "Sud", "kc_value": 1.0}, content_type="application/json")
    assert resp.status_code == 201
    assert Parcelle.objects.get(name="Sud").exploitation == exploitation


@pytest.mark.django_db
def test_detail_404_cross_tenant(client, user_exploitation):
    user, exploitation = user_exploitation
    other = User.objects.create_user(email="d@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Ferme D")
    p = Parcelle.objects.create(exploitation=other_exp, name="Secrète")
    client.force_login(user)
    resp = client.get(reverse("parcelles:detail", args=[p.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_campagnes_page_lists_and_filters(client, user_exploitation):
    """La page Campagnes agrège toutes les parcelles et filtre par libellé."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    nord = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    sud = Parcelle.objects.create(exploitation=exploitation, name="Sud", area=2)
    ParcelleCampagne.objects.create(parcelle=nord, libelle="2025/2026", culture="Vigne")
    ParcelleCampagne.objects.create(parcelle=sud, libelle="2025/2026", culture="Olivier")
    ParcelleCampagne.objects.create(parcelle=nord, libelle="2024/2025", culture="Blé")

    client.force_login(user)

    toutes = client.get(reverse("parcelles:campagnes"), {"campagne": ""})
    assert toutes.status_code == 200 and toutes.context["kpi_count"] == 3
    assert toutes.context["libelles"] == ["2025/2026", "2024/2025"]

    filtre = client.get(reverse("parcelles:campagnes"), {"campagne": "2025/2026"})
    assert filtre.context["kpi_count"] == 2 and filtre.context["kpi_parcelles"] == 2
    assert filtre.context["kpi_surface"] == 5 and filtre.context["kpi_cultures"] == 2
    assert "Blé" not in filtre.content.decode()


@pytest.mark.django_db
def test_campagnes_page_is_tenant_scoped(client, user_exploitation):
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    autre = User.objects.create_user(email="autre-camp@ex.com", password="pwd12345")
    autre_exploitation = Exploitation.objects.create(owner=autre, name="Ferme B", total_area=5)
    intruse = Parcelle.objects.create(exploitation=autre_exploitation, name="Intruse", area=1)
    ParcelleCampagne.objects.create(parcelle=intruse, libelle="2025/2026", culture="Colza")

    client.force_login(user)
    resp = client.get(reverse("parcelles:campagnes"))
    assert resp.context["kpi_count"] == 0 and "Intruse" not in resp.content.decode()


@pytest.mark.django_db
def test_campagne_new_creates_from_campagnes_page(client, user_exploitation):
    """Création d'une campagne hors fiche parcelle : la parcelle est choisie au formulaire."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    client.force_login(user)

    page = client.get(reverse("parcelles:campagne_new"))
    assert page.status_code == 200 and "Nord" in page.content.decode()

    resp = client.post(reverse("parcelles:campagne_new"), {
        "parcelle": parcelle.pk, "libelle": "2025/2026", "culture": "Vigne", "kc_value": 1.0,
    })
    campagne = ParcelleCampagne.objects.get(libelle="2025/2026")
    assert resp.status_code == 302 and campagne.parcelle == parcelle
    assert resp["Location"].endswith("/campagnes/?campagne=2025/2026")


@pytest.mark.django_db
def test_campagne_new_rejects_missing_or_foreign_parcelle(client, user_exploitation):
    """Sans parcelle valide, rien n'est créé — y compris pour une parcelle d'autrui."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    autre = User.objects.create_user(email="autre-new@ex.com", password="pwd12345")
    autre_exploitation = Exploitation.objects.create(owner=autre, name="Ferme B", total_area=5)
    intruse = Parcelle.objects.create(exploitation=autre_exploitation, name="Intruse", area=1)

    client.force_login(user)
    donnees = {"libelle": "2025/2026", "culture": "Vigne", "kc_value": 1.0}

    sans = client.post(reverse("parcelles:campagne_new"), donnees)
    assert sans.status_code == 200 and "Choisissez la parcelle" in sans.content.decode()

    volee = client.post(reverse("parcelles:campagne_new"), {**donnees, "parcelle": intruse.pk})
    assert volee.status_code == 200
    assert not ParcelleCampagne.objects.exists()


@pytest.mark.django_db
def test_campagne_new_redirects_when_no_parcelle(client, user_exploitation):
    """Sans aucune parcelle, la page renvoie vers la création de parcelle."""
    user, _exploitation = user_exploitation
    client.force_login(user)

    resp = client.get(reverse("parcelles:campagne_new"))
    assert resp.status_code == 302 and resp["Location"] == reverse("parcelles:list")


@pytest.mark.django_db
def test_campagne_type_culture_deduit_du_referentiel(client, user_exploitation):
    """Type laissé vide → repli sur la catégorie de la culture (agronomie)."""
    from agronomie.models import CultureKc
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    CultureKc.objects.create(nom="Vigne", categorie=CultureKc.Categorie.VIGNE)
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    campagne = ParcelleCampagne.objects.create(parcelle=parcelle, libelle="2025/2026")
    client.force_login(user)

    client.post(reverse("parcelles:campagne_edit", args=[campagne.pk]), {
        "libelle": "2025/2026", "culture": "Vigne", "type_culture": "", "kc_value": 1.0,
    })
    campagne.refresh_from_db()
    assert campagne.type_culture == "vigne" and campagne.type_culture_label == "Vigne"

    # Un type explicite prime sur la déduction.
    client.post(reverse("parcelles:campagne_edit", args=[campagne.pk]), {
        "libelle": "2025/2026", "culture": "Vigne", "type_culture": "fruits", "kc_value": 1.0,
    })
    campagne.refresh_from_db()
    assert campagne.type_culture == "fruits"


@pytest.mark.django_db
def test_type_culture_visible_sur_la_fiche_parcelle(client, user_exploitation):
    """Ce qui est saisi sur la campagne remonte sur /parcelles/<pk>/."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    ParcelleCampagne.objects.create(
        parcelle=parcelle, libelle="2025/2026", culture="Merlot", type_culture="vigne",
    )

    client.force_login(user)
    body = client.get(reverse("parcelles:detail", args=[parcelle.pk])).content.decode()
    assert "Type de culture" in body and "Vigne" in body


@pytest.mark.django_db
def test_campagne_delete_revient_sur_la_liste_des_campagnes(client, user_exploitation):
    """Suppression lancée depuis la page Campagnes → retour sur cette page."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    campagne = ParcelleCampagne.objects.create(parcelle=parcelle, libelle="2025/2026")
    url = reverse("parcelles:campagne_delete", args=[campagne.pk])
    client.force_login(user)

    confirmation = client.get(url, {"next": "campagnes"})
    assert confirmation.status_code == 200
    assert confirmation.context["retour_url"] == reverse("parcelles:campagnes")

    resp = client.post(url, {"next": "campagnes"})
    assert resp["Location"] == reverse("parcelles:campagnes")
    assert not ParcelleCampagne.objects.filter(pk=campagne.pk).exists()


@pytest.mark.django_db
def test_campagne_delete_depuis_la_parcelle_inchange(client, user_exploitation):
    """Sans ?next, la suppression continue de renvoyer sur la fiche parcelle."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3)
    campagne = ParcelleCampagne.objects.create(parcelle=parcelle, libelle="2025/2026")

    client.force_login(user)
    resp = client.post(reverse("parcelles:campagne_delete", args=[campagne.pk]))
    assert resp["Location"] == parcelle.get_absolute_url()


@pytest.mark.parametrize("jour,attendu", [
    ("2026-08-31", "2025/2026"),  # août : encore la campagne précédente
    ("2026-09-01", "2026/2027"),  # 1ᵉʳ septembre : bascule
    ("2026-12-15", "2026/2027"),
    ("2027-07-01", "2026/2027"),
])
def test_libelle_courant_bascule_en_septembre(jour, attendu):
    from datetime import date

    from parcelles.models import ParcelleCampagne

    annee, mois, num = (int(x) for x in jour.split("-"))
    assert ParcelleCampagne.libelle_courant(date(annee, mois, num)) == attendu


@pytest.mark.django_db
def test_type_agriculture_partage_entre_campagne_et_parcelle(client, user_exploitation):
    """Le type d'agriculture édité depuis la campagne est bien celui de la parcelle."""
    from parcelles.models import ParcelleCampagne

    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord", area=3, type_agriculture="bio")
    campagne = ParcelleCampagne.objects.create(parcelle=parcelle, libelle="2025/2026")
    client.force_login(user)

    # La valeur de la parcelle est pré-remplie sur l'écran campagne.
    page = client.get(reverse("parcelles:campagne_edit", args=[campagne.pk]))
    assert page.status_code == 200
    assert page.context["parcelle_form"]["type_agriculture"].value() == "bio"

    # La modifier depuis la campagne met à jour la parcelle.
    client.post(reverse("parcelles:campagne_edit", args=[campagne.pk]), {
        "libelle": "2025/2026", "culture": "Vigne", "kc_value": 1.0, "type_agriculture": "hve",
    })
    parcelle.refresh_from_db()
    assert parcelle.type_agriculture == "hve"

    # Et l'écran parcelle affiche la même valeur.
    edition = client.get(reverse("parcelles:edit", args=[parcelle.pk]))
    assert edition.context["form"]["type_agriculture"].value() == "hve"


@pytest.mark.django_db
def test_type_agriculture_depuis_nouvelle_campagne(client, user_exploitation):
    user, exploitation = user_exploitation
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Sud", area=2)
    client.force_login(user)

    client.post(reverse("parcelles:campagne_new"), {
        "parcelle": parcelle.pk, "libelle": "2025/2026", "kc_value": 1.0,
        "type_agriculture": "conversion",
    })
    parcelle.refresh_from_db()
    assert parcelle.type_agriculture == "conversion"
