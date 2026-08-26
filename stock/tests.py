"""Tests Stock : le niveau suit les mouvements, et rien ne franchit le tenant."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from exploitations.models import Exploitation
from stock.models import Article, Depot, Mouvement

User = get_user_model()


@pytest.fixture
def ferme(db):
    user = User.objects.create_user(email="stock@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Stock")
    return user, exploitation


@pytest.fixture
def article(ferme):
    _, exploitation = ferme
    return Article.objects.create(
        exploitation=exploitation, nom="Ammonitrate", unite="kg",
        quantite=1000, seuil_alerte=200, prix_unitaire=0.5,
    )


@pytest.mark.django_db
def test_mouvement_deplace_le_stock_et_garde_le_niveau_atteint(ferme, article):
    _, exploitation = ferme

    entree = Mouvement.objects.create(
        exploitation=exploitation, article=article,
        type_mouvement=Mouvement.Type.ENTREE, quantite=500,
    )
    sortie = Mouvement.objects.create(
        exploitation=exploitation, article=article,
        type_mouvement=Mouvement.Type.SORTIE, quantite=200,
    )

    assert entree.quantite_apres == 1500
    assert sortie.quantite_apres == 1300
    article.refresh_from_db()
    assert article.quantite == 1300


@pytest.mark.django_db
def test_correction_aligne_le_stock_sur_le_niveau_constate(ferme, article):
    _, exploitation = ferme

    Mouvement.objects.create(
        exploitation=exploitation, article=article,
        type_mouvement=Mouvement.Type.CORRECTION, quantite=940,
    )

    article.refresh_from_db()
    assert article.quantite == 940


@pytest.mark.django_db
def test_alerte_au_seuil_et_valeur_du_stock(article):
    assert article.en_alerte is False
    assert article.valeur == 500

    article.quantite = 150
    assert article.en_alerte is True


@pytest.mark.django_db
def test_sortie_superieure_au_stock_refusee(client, ferme, article):
    user, _ = ferme
    client.force_login(user)

    resp = client.post(reverse("stock:mouvement_create"), {
        "article": article.pk, "type_mouvement": "sortie", "quantite": "1500",
    })

    assert resp.status_code == 302
    assert Mouvement.objects.count() == 0
    article.refresh_from_db()
    assert article.quantite == 1000


@pytest.mark.django_db
def test_stock_initial_passe_par_un_mouvement(client, ferme):
    user, _ = ferme
    client.force_login(user)

    client.post(reverse("stock:article_save"), {
        "nom": "Gasoil non routier", "categorie": "carburant", "unite": "l", "quantite": "2000",
    })

    article = Article.objects.get(nom="Gasoil non routier")
    assert article.quantite == 2000
    mouvement = article.mouvements.get()
    assert mouvement.type_mouvement == Mouvement.Type.ENTREE
    assert mouvement.quantite_apres == 2000


@pytest.mark.django_db
def test_article_dune_autre_exploitation_hors_de_portee(client, ferme):
    user, _ = ferme
    voisin = User.objects.create_user(email="voisin@ex.com", password="pwd12345")
    ailleurs = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    article = Article.objects.create(exploitation=ailleurs, nom="Semences maïs", quantite=10)
    client.force_login(user)

    liste = client.get(reverse("stock:articles"))
    assert not list(liste.context["articles"])

    suppression = client.post(reverse("stock:article_delete", args=[article.pk]))
    assert suppression.status_code == 404
    assert Article.objects.filter(pk=article.pk).exists()


@pytest.mark.django_db
def test_depot_supprime_laisse_ses_articles(client, ferme):
    user, exploitation = ferme
    depot = Depot.objects.create(exploitation=exploitation, nom="Hangar nord")
    article = Article.objects.create(exploitation=exploitation, nom="Orge", depot=depot, quantite=5)
    client.force_login(user)

    client.post(reverse("stock:depot_delete", args=[depot.pk]))

    article.refresh_from_db()
    assert article.depot is None


# ── Récoltes : le fait de production entre en stock ──────────────────

@pytest.mark.django_db
def test_recolte_ouvre_larticle_et_le_remplit(client, ferme):
    from finances.models import Recolte
    from parcelles.models import Parcelle

    user, exploitation = ferme
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Le Clos")
    client.force_login(user)

    client.post(reverse("stock:recolte_create"), {
        "parcelle": parcelle.pk, "nom_article": "Tomates cœur de bœuf", "unite": "kg",
        "quantite_kg": "480", "qualite": "extra", "prix_unitaire": "2,40",
    })

    article = Article.objects.get(nom="Tomates cœur de bœuf")
    assert article.categorie == Article.Categorie.RECOLTE
    assert article.quantite == 480
    assert article.prix_unitaire == 2.4

    recolte = Recolte.objects.get()
    assert recolte.parcelle == parcelle and recolte.quantite_kg == 480
    entree = article.mouvements.get()
    assert entree.motif == Mouvement.Motif.RECOLTE
    assert entree.recolte == recolte and entree.quantite_apres == 480


@pytest.mark.django_db
def test_recolte_en_tonnes_convertie_et_valorisee(client, ferme):
    from parcelles.models import Parcelle

    user, exploitation = ferme
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Grand champ")
    client.force_login(user)

    client.post(reverse("stock:recolte_create"), {
        "parcelle": parcelle.pk, "nom_article": "Blé tendre", "unite": "t",
        "quantite_kg": "25000", "prix_unitaire": "0,22",
    })

    article = Article.objects.get(nom="Blé tendre")
    assert article.quantite == 25          # 25 000 kg tenus en tonnes
    assert article.prix_unitaire == 220     # 0,22 €/kg valorisé à la tonne


@pytest.mark.django_db
def test_recolte_refusee_si_larticle_nest_pas_pesable(client, ferme):
    from parcelles.models import Parcelle

    user, exploitation = ferme
    parcelle = Parcelle.objects.create(exploitation=exploitation, name="Verger")
    cagettes = Article.objects.create(exploitation=exploitation, nom="Pommes", unite="sac")
    client.force_login(user)

    resp = client.post(reverse("stock:recolte_create"), {
        "parcelle": parcelle.pk, "article": cagettes.pk, "quantite_kg": "300",
    }, follow=True)

    assert b"kg ou en tonnes" in resp.content
    cagettes.refresh_from_db()
    assert cagettes.quantite == 0
    assert Mouvement.objects.count() == 0


@pytest.mark.django_db
def test_recolte_sur_parcelle_dune_autre_exploitation_refusee(client, ferme):
    from finances.models import Recolte
    from parcelles.models import Parcelle

    user, _ = ferme
    voisin = User.objects.create_user(email="voisine@ex.com", password="pwd12345")
    ailleurs = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    parcelle = Parcelle.objects.create(exploitation=ailleurs, name="Chez le voisin")
    client.force_login(user)

    client.post(reverse("stock:recolte_create"), {
        "parcelle": parcelle.pk, "nom_article": "Colza", "quantite_kg": "100",
    })

    assert Recolte.objects.count() == 0
    assert Article.objects.count() == 0
