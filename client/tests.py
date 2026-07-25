"""Tests Clients : fiches clients et cloisonnement par exploitation."""

import pytest
from django.contrib.auth import get_user_model

from client.models import Client
from exploitations.models import Exploitation

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="cl@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Cl", total_area=12)
    return user, exploitation


@pytest.mark.django_db
def test_client_create_and_detail(client, setup):
    user, exploitation = setup
    client.force_login(user)

    resp = client.post("/clients/nouveau/", {
        "nom": "Coopérative du Ventoux", "categorie": "professionnel",
        "type_client": "cooperative", "statut": "actif", "siret": "12345678900012",
        "numero_voie": "12", "type_voie": "rue", "voie": "des Vergers",
        "ville": "Carpentras", "code_postal": "84200", "pays": "France",
        "ca_annuel": "12 500,50", "delai_paiement_jours": "30",
    })
    fiche = Client.objects.get(nom="Coopérative du Ventoux")
    assert resp.status_code == 302 and resp["Location"] == f"/clients/{fiche.pk}/"
    assert fiche.exploitation == exploitation
    assert fiche.ca_annuel == 12500.50 and fiche.delai_paiement_jours == 30
    assert fiche.adresse_ligne == "12 Rue des Vergers"
    assert fiche.adresse_complete == "12 Rue des Vergers, 84200 Carpentras, France"
    assert fiche.type_label == "Coopérative" and fiche.siret == "12345678900012"

    detail = client.get(f"/clients/{fiche.pk}/")
    body = detail.content.decode()
    assert detail.status_code == 200 and "Carpentras" in body
    # La modale d'édition embarque les outils dictée + reformulation IA sur les notes.
    assert "hsDictate(this, 'client-notes')" in body
    assert "/assistant/reformuler/" in body


@pytest.mark.django_db
def test_client_edit(client, setup):
    user, exploitation = setup
    fiche = Client.objects.create(exploitation=exploitation, nom="Grossiste Sud")
    client.force_login(user)

    client.post(f"/clients/{fiche.pk}/modifier/", {
        "nom": "Grossiste Sud SA", "statut": "actif", "email": "contact@sud.fr",
    })
    fiche.refresh_from_db()
    assert fiche.nom == "Grossiste Sud SA" and fiche.statut == Client.Statut.ACTIF
    assert fiche.email == "contact@sud.fr"


@pytest.mark.django_db
def test_clients_list_kpis_are_tenant_scoped(client, setup):
    user, exploitation = setup
    autre = User.objects.create_user(email="autre@ex.com", password="pwd12345")
    autre_exploitation = Exploitation.objects.create(owner=autre, name="Ferme Autre", total_area=5)

    Client.objects.create(exploitation=exploitation, nom="Mien", statut="actif", ca_annuel=1000)
    intrus = Client.objects.create(exploitation=autre_exploitation, nom="Intrus", ca_annuel=9999)

    client.force_login(user)
    resp = client.get("/clients/")
    body = resp.content.decode()
    assert resp.status_code == 200 and "Mien" in body and "Intrus" not in body
    assert resp.context["kpi_count"] == 1 and resp.context["kpi_ca"] == 1000

    # La fiche d'une autre exploitation reste inaccessible.
    assert client.get(f"/clients/{intrus.pk}/").status_code == 404
    assert client.post(f"/clients/{intrus.pk}/supprimer/").status_code == 404


@pytest.mark.django_db
def test_particulier_ignores_professional_fields(client, setup):
    """Un particulier n'a ni sous-catégorie, ni SIRET, ni TVA — même si postés."""
    user, exploitation = setup
    client.force_login(user)

    client.post("/clients/nouveau/", {
        "nom": "Dupont", "prenom": "Marie", "categorie": "particulier",
        "type_client": "grossiste", "siret": "12345678900012",
        "tva_intracom": "FR40303265045", "ville": "Avignon",
        "delai_paiement_jours": "45", "ca_annuel": "9000",
    })
    fiche = Client.objects.get(nom="Dupont")
    assert fiche.est_particulier and fiche.type_label == "Particulier"
    assert fiche.nom_complet == "Marie Dupont"
    assert fiche.type_client == "" and fiche.siret == "" and fiche.tva_intracom == ""
    assert fiche.delai_paiement_jours is None and fiche.ca_annuel is None

    # Le passage en professionnel réactive bien ces champs.
    client.post(f"/clients/{fiche.pk}/modifier/", {
        "nom": "Dupont SARL", "prenom": "Marie", "categorie": "professionnel",
        "type_client": "grossiste", "siret": "12345678900012", "delai_paiement_jours": "45",
    })
    fiche.refresh_from_db()
    assert fiche.type_label == "Grossiste" and fiche.siret == "12345678900012"
    assert fiche.delai_paiement_jours == 45
    # Le prénom est propre aux particuliers : il disparaît du nom affiché.
    assert fiche.prenom == "" and fiche.nom_complet == "Dupont SARL"


@pytest.mark.django_db
def test_clients_requires_login(client):
    resp = client.get("/clients/")
    assert resp.status_code == 302 and "/login" in resp["Location"]
