"""Tests opérations : machines/interventions API + intent IA creer_intervention."""

import pytest
from django.contrib.auth import get_user_model

from exploitations.models import Exploitation
from interventions.models import Intervention
from operations.models import Machine
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="op@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Op")
    return user, exploitation


@pytest.mark.django_db
def test_machine_api_create_scoped(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.post("/api/machines/", {"name": "Tracteur JD", "type": "tracteur_standard"}, content_type="application/json")
    assert resp.status_code == 201
    assert Machine.objects.get(name="Tracteur JD").exploitation == exploitation


@pytest.mark.django_db
def test_intervention_api_sets_user_and_scope(client, setup):
    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Sud")
    client.force_login(user)
    resp = client.post(
        "/api/interventions/",
        {"intervention_type": "taille", "parcelle": parcelle.id, "start_time": "2026-06-23T08:00:00Z"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    iv = Intervention.objects.get(parcelle=parcelle)
    assert iv.user == user and iv.exploitation == exploitation


@pytest.mark.django_db
def test_ai_intent_creates_intervention(setup, monkeypatch):
    from ia import services

    user, exploitation = setup
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Nord")
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)
    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda messages, **kw: {
            "response": "Intervention créée", "intent": "creer_intervention", "needs_more_info": False,
            "data": {"interventionType": "taille", "parcelleName": "Nord", "title": "Taille abricotiers"},
        },
    )
    result = services.execute_intent(exploitation, user, "Taille des abricotiers parcelle Nord")
    assert result["created"] is True and result["entity"]["type"] == "intervention"
    iv = Intervention.objects.get(exploitation=exploitation)
    assert iv.parcelle == parcelle and iv.intervention_type == "taille" and iv.source == "ai"


@pytest.mark.django_db
def test_catalogue_engins_readonly(client, setup):
    user, _ = setup
    client.force_login(user)
    # Lecture OK (référentiel global, vide ici)
    assert client.get("/api/catalogue-engins/").status_code == 200
    # Écriture interdite (ReadOnly)
    assert client.post("/api/catalogue-engins/", {"marque": "X", "modele": "Y", "type": "tracteur"},
                       content_type="application/json").status_code == 405


# ── Parc matériel : vocabulaire partagé et saisie depuis la page ──────


@pytest.mark.django_db
def test_vocabulaire_partage_entre_machine_et_catalogue():
    """Un semoir monograine porte le même code des deux côtés."""
    from operations.materiel import FAMILLE_PAR_TYPE, Famille, TypeMateriel
    from operations.models import CatalogueEngin

    assert Machine.Type is CatalogueEngin.Type is TypeMateriel
    # Chaque type appartient à une famille et à une seule.
    assert set(FAMILLE_PAR_TYPE) == set(TypeMateriel)
    assert FAMILLE_PAR_TYPE[TypeMateriel.SEMOIR_MONOGRAINE] == Famille.SEMIS
    # La distinction qui porte les heures et la carte grise.
    assert Machine(type=TypeMateriel.TRACTEUR_VIGNERON).est_automoteur
    assert not Machine(type=TypeMateriel.HERSE_ETRILLE).est_automoteur


@pytest.mark.django_db
def test_parc_materiel_ajout(client, setup):
    user, exploitation = setup
    client.force_login(user)

    vide = client.get("/parc-materiel/")
    assert vide.status_code == 200
    assert "Votre parc est vide." in vide.content.decode()

    resp = client.post("/parc-materiel/ajouter/", {
        "name": "Fendt 313", "type": "tracteur_vigneron", "brand": "Fendt",
        "model": "313 Vario", "serial_number": "FN-77120", "purchase_date": "2021-04-15",
        "total_hours": "1 250,5", "status": "operational", "notes": "Étroit, rangs de 2 m.",
    })
    assert resp.status_code == 302 and resp["Location"] == "/parc-materiel/"

    engin = Machine.objects.get(name="Fendt 313")
    assert engin.exploitation == exploitation
    assert engin.type == "tracteur_vigneron" and engin.est_automoteur
    assert engin.total_hours == 1250.5
    assert str(engin.purchase_date) == "2021-04-15"

    page = client.get("/parc-materiel/").content.decode()
    assert "Fendt 313" in page
    # La fiche s'affiche sous sa famille, pas en vrac.
    assert "Automoteurs" in page
    assert "Tracteur vigneron (étroit)" in page


@pytest.mark.django_db
def test_parc_materiel_refuse_un_type_inconnu(client, setup):
    user, _exploitation = setup
    client.force_login(user)
    client.post("/parc-materiel/ajouter/", {"name": "Engin fantôme", "type": "soucoupe"})
    assert not Machine.objects.filter(name="Engin fantôme").exists()


@pytest.mark.django_db
def test_parc_materiel_classe_par_famille(client, setup):
    user, exploitation = setup
    client.force_login(user)
    Machine.objects.create(exploitation=exploitation, name="Charrue Kuhn", type="charrue")
    Machine.objects.create(exploitation=exploitation, name="Tank 3000 L", type="tank_a_lait")

    resp = client.get("/parc-materiel/")
    # L'ordre des sections suit celui du vocabulaire : le sol avant l'élevage.
    # On lit le contexte, pas le HTML : « Élevage » est aussi un item de la nav.
    sections = [str(libelle) for libelle, _lot in resp.context["familles"]]
    assert sections == ["Travail du sol", "Élevage"]
    assert [m.name for _l, lot in resp.context["familles"] for m in lot] == ["Charrue Kuhn", "Tank 3000 L"]

    page = resp.content.decode()
    assert "Charrue Kuhn" in page and "Tank 3000 L" in page


@pytest.mark.django_db
def test_parc_materiel_suppression_cloisonnee(client, setup):
    user, exploitation = setup
    voisin = User.objects.create_user(email="voisin@ex.com", password="pwd12345")
    ferme_voisine = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    sienne = Machine.objects.create(exploitation=ferme_voisine, name="Pivot du voisin", type="pivot")
    mienne = Machine.objects.create(exploitation=exploitation, name="Ma pompe", type="pompe")

    client.force_login(user)
    assert client.post(f"/parc-materiel/{sienne.pk}/supprimer/").status_code == 404
    assert Machine.objects.filter(pk=sienne.pk).exists()

    assert client.post(f"/parc-materiel/{mienne.pk}/supprimer/").status_code == 302
    assert not Machine.objects.filter(pk=mienne.pk).exists()


@pytest.mark.django_db
def test_marques_suggerees_suivent_la_famille(client, setup):
    """Le type choisi commande les marques proposées, sans jamais contraindre."""
    from operations.materiel import Famille, TypeMateriel

    user, _exploitation = setup
    client.force_login(user)
    resp = client.get("/parc-materiel/")

    marques = resp.context["marques_par_famille"]
    familles = resp.context["famille_par_type"]

    # Chaque famille a son entrée, fût-elle vide ; chaque type sa famille.
    assert set(marques) == set(Famille.values)
    assert set(familles) == set(TypeMateriel.values)

    assert familles["tank_a_lait"] == "elevage"
    assert familles["charrue"] == "travail_du_sol"
    assert "DeLaval" in marques["elevage"]
    assert "DeLaval" not in marques["travail_du_sol"]
    assert "Lemken" in marques["travail_du_sol"]
    assert marques["autre"] == []

    # Une liste déroulante visible, et une porte de sortie vers la saisie libre.
    page = resp.content.decode()
    assert '<select id="m-marque" name="brand"' in page
    assert 'Autre marque' in page and 'name="brand_autre"' in page


@pytest.mark.django_db
def test_une_marque_hors_liste_est_acceptee(client, setup):
    """« Autre marque… » ouvre la saisie libre ; la sentinelle ne descend pas en base."""
    user, _exploitation = setup
    client.force_login(user)

    # Marque choisie dans la liste.
    client.post("/parc-materiel/ajouter/", {
        "name": "Le tracteur", "type": "tracteur_standard", "brand": "Fendt"})
    assert Machine.objects.get(name="Le tracteur").brand == "Fendt"

    # Marque hors liste : constructeur local, engin rebadgé, remorque de ferme.
    client.post("/parc-materiel/ajouter/", {
        "name": "Remorque de la ferme", "type": "remorque",
        "brand": "__autre__", "brand_autre": "Atelier du village"})
    assert Machine.objects.get(name="Remorque de la ferme").brand == "Atelier du village"

    # Famille sans suggestion : le champ libre est seul, et suffit.
    client.post("/parc-materiel/ajouter/", {
        "name": "Engin indéfinissable", "type": "autre", "brand_autre": "Bricolage maison"})
    assert Machine.objects.get(name="Engin indéfinissable").brand == "Bricolage maison"

    assert not Machine.objects.filter(brand="__autre__").exists()


@pytest.mark.django_db
def test_heures_saisie_au_curseur_et_au_champ(client, setup):
    """Le curseur approche, le champ tranche ; un seul des deux est soumis."""
    user, _exploitation = setup
    client.force_login(user)
    page = client.get("/parc-materiel/").content.decode()
    assert 'type="range"' in page
    # Seul le champ numérique porte le name : le curseur ne double pas l'envoi.
    assert page.count('name="total_hours"') == 1
    # Pleine échelle du curseur, fixée à 300 000 h.
    assert "300000" in page
    # Un {# … #} à cheval sur deux lignes n'est pas un commentaire pour Django :
    # il s'affiche en clair. Aucun marqueur de gabarit ne doit atteindre la page.
    assert "{#" not in page and "#}" not in page

    client.post("/parc-materiel/ajouter/", {
        "name": "Pompe de forage", "type": "pompe", "total_hours": "8400"})
    assert Machine.objects.get(name="Pompe de forage").total_hours == 8400


@pytest.mark.django_db
def test_les_heures_ne_sont_pas_reservees_aux_automoteurs(client, setup):
    """Une pompe a un compteur : ses heures doivent s'afficher, pas un tiret."""
    user, exploitation = setup
    client.force_login(user)
    Machine.objects.create(exploitation=exploitation, name="Pompe Grundfos",
                           type="pompe", total_hours=8400)
    Machine.objects.create(exploitation=exploitation, name="Charrue nue",
                           type="charrue", total_hours=0)

    page = client.get("/parc-materiel/").content.decode()
    assert "8400" in page          # la pompe montre son compteur…
    assert not Machine(type="pompe").est_automoteur   # …bien qu'elle ne roule pas seule


# ── Détention : à qui appartient l'engin ─────────────────────────────


@pytest.fixture
def cuma(setup):
    """Une CUMA enregistrée dans les relations de l'exploitation."""
    from client.models import Partenaire

    _user, exploitation = setup
    return Partenaire.objects.create(
        exploitation=exploitation, type_partenaire=Partenaire.Type.CUMA,
        nom="CUMA des Dentelles")


@pytest.mark.django_db
def test_materiel_detenu_en_cuma(client, setup, cuma):
    user, exploitation = setup
    client.force_login(user)

    client.post("/parc-materiel/ajouter/", {
        "name": "Moissonneuse partagée", "type": "moissonneuse_batteuse",
        "detention": "cuma", "proprietaire": str(cuma.pk)})

    engin = Machine.objects.get(name="Moissonneuse partagée")
    assert engin.est_en_cuma
    assert engin.proprietaire == cuma
    # La CUMA voit son matériel depuis sa fiche.
    assert list(cuma.materiels.all()) == [engin]

    page = client.get("/parc-materiel/").content.decode()
    assert "En CUMA" in page and "CUMA des Dentelles" in page


@pytest.mark.django_db
def test_materiel_en_propre_par_defaut(client, setup, cuma):
    """Sans rien préciser, l'engin est à la ferme — et sans propriétaire tiers."""
    user, _exploitation = setup
    client.force_login(user)
    client.post("/parc-materiel/ajouter/", {"name": "Charrue", "type": "charrue"})

    engin = Machine.objects.get(name="Charrue")
    assert engin.detention == Machine.Detention.PROPRE
    assert not engin.est_en_cuma and engin.proprietaire is None

    # « En propre » ignore un propriétaire envoyé par erreur.
    client.post("/parc-materiel/ajouter/", {
        "name": "Rouleau", "type": "rouleau",
        "detention": "propre", "proprietaire": str(cuma.pk)})
    assert Machine.objects.get(name="Rouleau").proprietaire is None


@pytest.mark.django_db
def test_le_proprietaire_ne_peut_venir_d_une_autre_ferme(client, setup):
    """Cloisonnement : la CUMA du voisin n'est pas rattachable par un POST forgé."""
    from client.models import Partenaire

    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin2@ex.com", password="pwd12345")
    ferme_voisine = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    cuma_du_voisin = Partenaire.objects.create(
        exploitation=ferme_voisine, type_partenaire=Partenaire.Type.CUMA, nom="CUMA d'à côté")

    client.force_login(user)
    client.post("/parc-materiel/ajouter/", {
        "name": "Engin convoité", "type": "ensileuse",
        "detention": "cuma", "proprietaire": str(cuma_du_voisin.pk)})

    engin = Machine.objects.get(name="Engin convoité")
    assert engin.detention == "cuma"       # le mode est retenu…
    assert engin.proprietaire is None      # …mais le tiers d'à côté est écarté


@pytest.mark.django_db
def test_une_detention_inconnue_retombe_sur_en_propre(client, setup):
    user, _exploitation = setup
    client.force_login(user)
    client.post("/parc-materiel/ajouter/", {
        "name": "Engin flou", "type": "benne", "detention": "en_fiducie"})
    assert Machine.objects.get(name="Engin flou").detention == Machine.Detention.PROPRE


@pytest.mark.django_db
def test_notes_offrent_la_reformulation_ia(client, setup):
    """Le champ Notes porte les mêmes outils que les autres notes de l'app."""
    user, _exploitation = setup
    client.force_login(user)
    page = client.get("/parc-materiel/").content.decode()
    assert "hsRewrite(this, 'm-notes'" in page
    assert "/assistant/reformuler/" in page
