"""Tests Aquaculture : installations, lots, biomasse et cloisonnement."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from aquaculture.models import Bassin, Lot
from exploitations.models import Exploitation

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="aqua@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Aqua", total_area=8)
    return user, exploitation


@pytest.mark.django_db
def test_bassin_create_and_detail(client, setup):
    user, exploitation = setup
    client.force_login(user)

    resp = client.post(reverse("aquaculture:create"), {
        "nom": "Étang du moulin", "type_bassin": "etang", "statut": "en_service",
        "source_eau": "riviere", "surface_m2": "1 200", "volume_m3": "1800,5",
        "profondeur_m": "1,5", "temperature_cible_c": "14",
    })
    bassin = Bassin.objects.get(nom="Étang du moulin")
    assert resp.status_code == 302 and resp["Location"] == f"/aquaculture/{bassin.pk}/"
    assert bassin.exploitation == exploitation
    assert bassin.surface_m2 == 1200 and bassin.volume_m3 == 1800.5

    detail = client.get(reverse("aquaculture:detail", args=[bassin.pk]))
    assert detail.status_code == 200 and "Rivière" in detail.content.decode()


@pytest.mark.django_db
def test_biomasse_et_densite_ne_comptent_que_les_lots_en_elevage(client, setup):
    user, exploitation = setup
    bassin = Bassin.objects.create(exploitation=exploitation, nom="Bassin 1", volume_m3=100)

    # 5 000 truites à 120 g = 600 kg en élevage.
    Lot.objects.create(bassin=bassin, espece="Truite", effectif=5000, poids_moyen_g=120)
    # Un lot récolté et un lot sans pesée ne pèsent pas dans la biomasse.
    Lot.objects.create(bassin=bassin, espece="Carpe", effectif=200, poids_moyen_g=800, statut=Lot.Statut.RECOLTE)
    Lot.objects.create(bassin=bassin, espece="Tanche", effectif=300)

    assert bassin.biomasse_kg == 600.0
    assert bassin.densite_kg_m3 == 6.0

    client.force_login(user)
    liste = client.get(reverse("aquaculture:bassins"))
    assert liste.context["kpi_biomasse"] == 600
    assert liste.context["kpi_lots"] == 2  # Truite et Tanche, pas la carpe récoltée


@pytest.mark.django_db
def test_densite_sans_volume_reste_indeterminee(setup):
    _user, exploitation = setup
    bassin = Bassin.objects.create(exploitation=exploitation, nom="Cage mer")
    Lot.objects.create(bassin=bassin, espece="Bar", effectif=1000, poids_moyen_g=300)

    assert bassin.biomasse_kg == 300.0 and bassin.densite_kg_m3 is None


@pytest.mark.django_db
def test_lot_create_et_suppression(client, setup):
    user, exploitation = setup
    bassin = Bassin.objects.create(exploitation=exploitation, nom="Raceway")
    client.force_login(user)

    client.post(reverse("aquaculture:lot_create", args=[bassin.pk]), {
        "espece": "Truite arc-en-ciel", "souche": "Val", "effectif": "800",
        "poids_moyen_g": "95", "date_mise_en_charge": "2026-03-15", "statut_lot": "en_elevage",
    })
    lot = Lot.objects.get(espece="Truite arc-en-ciel")
    assert lot.bassin == bassin and lot.effectif == 800
    assert str(lot.date_mise_en_charge) == "2026-03-15"

    client.post(reverse("aquaculture:lot_delete", args=[lot.pk]))
    assert not Lot.objects.filter(pk=lot.pk).exists()


@pytest.mark.django_db
def test_aquaculture_est_cloisonnee_par_exploitation(client, setup):
    user, exploitation = setup
    autre = User.objects.create_user(email="autre-aqua@ex.com", password="pwd12345")
    autre_exploitation = Exploitation.objects.create(owner=autre, name="Ferme B", total_area=4)

    Bassin.objects.create(exploitation=exploitation, nom="Mien")
    intrus = Bassin.objects.create(exploitation=autre_exploitation, nom="Intrus")

    client.force_login(user)
    body = client.get(reverse("aquaculture:bassins")).content.decode()
    assert "Mien" in body and "Intrus" not in body

    assert client.get(reverse("aquaculture:detail", args=[intrus.pk])).status_code == 404
    assert client.post(reverse("aquaculture:delete", args=[intrus.pk])).status_code == 404


@pytest.mark.django_db
def test_aquaculture_requires_login(client):
    resp = client.get(reverse("aquaculture:bassins"))
    assert resp.status_code == 302 and "/login" in resp["Location"]


# ── Référentiel espèces & souches ───────────────────────────────────

@pytest.mark.django_db
def test_referentiel_espece_et_souche(client, setup):
    from aquaculture.models import EspeceAquacole, Souche

    user, _exploitation = setup
    client.force_login(user)

    client.post(reverse("aquaculture:espece_create"), {
        "nom": "Truite arc-en-ciel", "nom_scientifique": "Oncorhynchus mykiss",
        "famille": "poisson_eau_douce", "milieu": "douce", "production": "chair",
        "duree_cycle_jours": "540", "temperature_optimale_c": "14,5",
    })
    espece = EspeceAquacole.objects.get(nom="Truite arc-en-ciel")
    assert espece.milieu == "douce" and espece.temperature_optimale_c == 14.5
    assert espece.duree_cycle_jours == 540

    client.post(reverse("aquaculture:souche_create"), {
        "espece": espece.pk, "nom": "Souche du Val", "aptitude": "Chair",
        "livree": "Argentée", "croissance": "Rapide", "note": "4,5", "nb_avis": "12",
    })
    souche = Souche.objects.get(nom="Souche du Val")
    assert souche.espece == espece and souche.livree == "Argentée"
    assert souche.croissance == "Rapide" and souche.note == 4.5

    page = client.get(reverse("aquaculture:especes"))
    donnees = page.context["especes_json"][0]
    assert page.status_code == 200
    assert donnees["nbSouches"] == 1 and donnees["souches"][0]["livree"] == "Argentée"
    assert donnees["milieuLabel"] == "Eau douce"


@pytest.mark.django_db
def test_supprimer_une_espece_emporte_ses_souches(client, setup):
    from aquaculture.models import EspeceAquacole, Souche

    user, _exploitation = setup
    espece = EspeceAquacole.objects.create(nom="Huître creuse", famille="coquillages")
    Souche.objects.create(espece=espece, nom="Diploïde")

    client.force_login(user)
    client.post(reverse("aquaculture:espece_delete", args=[espece.pk]))
    assert not EspeceAquacole.objects.exists() and not Souche.objects.exists()


@pytest.mark.django_db
def test_referentiel_requires_login(client):
    resp = client.get(reverse("aquaculture:especes"))
    assert resp.status_code == 302 and "/login" in resp["Location"]
