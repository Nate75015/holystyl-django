"""Tests Vente directe : ce que la vitrine montre, et ce qu'elle refuse de montrer."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from exploitations.models import Exploitation
from stock.models import Article
from vente.models import Boutique, Produit

User = get_user_model()


@pytest.fixture
def ferme(db):
    user = User.objects.create_user(email="paysan@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme du Clos", city="Avignon")
    boutique = Boutique.objects.create(exploitation=exploitation, titre="La Ferme du Clos", est_ouverte=True)
    return user, exploitation, boutique


@pytest.fixture
def tomates(ferme):
    _, exploitation, _ = ferme
    article = Article.objects.create(exploitation=exploitation, nom="Tomates", unite="kg", quantite=48)
    return Produit.objects.create(
        exploitation=exploitation, article=article, nom="Colis de tomates",
        categorie=Produit.Categorie.LEGUME, unite_vente=Produit.UniteVente.COLIS,
        conditionnement=5, prix_ttc=12, statut=Produit.Statut.EN_LIGNE,
    )


@pytest.mark.django_db
def test_slugs_uniques_et_lisibles(ferme):
    _user, _exploitation, boutique = ferme
    assert boutique.slug == "la-ferme-du-clos"

    voisin = User.objects.create_user(email="v@ex.com", password="pwd12345")
    autre = Exploitation.objects.create(owner=voisin, name="La Ferme du Clos")
    doublon = Boutique.objects.create(exploitation=autre, titre="La Ferme du Clos")
    assert doublon.slug == "la-ferme-du-clos-2"


@pytest.mark.django_db
def test_disponibilite_convertie_en_unites_de_vente(tomates):
    # 48 kg en stock, colis de 5 kg → 9 colis servables, pas 48.
    assert tomates.disponible == 9
    assert tomates.est_epuise is False

    tomates.article.quantite = 3
    tomates.article.save()
    assert tomates.disponible == 0 and tomates.est_epuise is True


@pytest.mark.django_db
def test_produit_sur_commande_nest_pas_epuise(ferme):
    _, exploitation, _ = ferme
    produit = Produit.objects.create(exploitation=exploitation, nom="Agneau de lait", prix_ttc=90)
    # Sans article rattaché, la disponibilité est inconnue — surtout pas nulle.
    assert produit.disponible is None and produit.est_epuise is False


@pytest.mark.django_db
def test_vitrine_visible_par_un_visiteur_anonyme(client, ferme, tomates):
    _, _, boutique = ferme

    marche = client.get(reverse("vente:marche"))
    assert marche.status_code == 200
    assert b"Colis de tomates" in marche.content

    vitrine = client.get(boutique.get_absolute_url())
    assert vitrine.status_code == 200
    assert b"La Ferme du Clos" in vitrine.content

    fiche = client.get(tomates.get_absolute_url())
    assert fiche.status_code == 200


@pytest.mark.django_db
def test_boutique_fermee_disparait_entierement(client, ferme, tomates):
    _, _, boutique = ferme
    boutique.est_ouverte = False
    boutique.save()

    assert client.get(boutique.get_absolute_url()).status_code == 404
    assert client.get(tomates.get_absolute_url()).status_code == 404
    assert b"Colis de tomates" not in client.get(reverse("vente:marche")).content


@pytest.mark.django_db
def test_brouillon_et_produit_discret_restent_hors_du_marche(client, ferme, tomates):
    _, exploitation, boutique = ferme
    brouillon = Produit.objects.create(
        exploitation=exploitation, nom="Confiture", prix_ttc=6, statut=Produit.Statut.BROUILLON
    )
    tomates.visible_marche = False
    tomates.save()

    marche = client.get(reverse("vente:marche")).content
    assert b"Colis de tomates" not in marche and b"Confiture" not in marche

    # Discret n'est pas retiré : la boutique de la ferme le montre toujours.
    vitrine = client.get(boutique.get_absolute_url()).content
    assert b"Colis de tomates" in vitrine and b"Confiture" not in vitrine
    assert client.get(brouillon.get_absolute_url()).status_code == 404


@pytest.mark.django_db
def test_recherche_et_filtre_par_categorie(client, ferme, tomates):
    _, exploitation, _ = ferme
    Produit.objects.create(
        exploitation=exploitation, nom="Miel de lavande", categorie=Produit.Categorie.MIEL,
        prix_ttc=9, statut=Produit.Statut.EN_LIGNE,
    )

    trouve = client.get(reverse("vente:marche"), {"q": "lavande"}).content
    assert b"Miel de lavande" in trouve and b"Colis de tomates" not in trouve

    legumes = client.get(reverse("vente:marche_categorie", args=["legume"])).content
    assert b"Colis de tomates" in legumes and b"Miel de lavande" not in legumes


@pytest.mark.django_db
def test_publier_ouvre_la_boutique_et_exige_un_prix(client, ferme):
    user, exploitation, boutique = ferme
    boutique.est_ouverte = False
    boutique.save()
    gratuit = Produit.objects.create(exploitation=exploitation, nom="Paille", prix_ttc=0)
    client.force_login(user)

    client.post(reverse("vente:produit_publier", args=[gratuit.pk]))
    gratuit.refresh_from_db()
    boutique.refresh_from_db()
    assert gratuit.statut == Produit.Statut.BROUILLON and boutique.est_ouverte is False

    gratuit.prix_ttc = 4
    gratuit.save()
    client.post(reverse("vente:produit_publier", args=[gratuit.pk]))
    gratuit.refresh_from_db()
    boutique.refresh_from_db()
    assert gratuit.statut == Produit.Statut.EN_LIGNE and boutique.est_ouverte is True


@pytest.mark.django_db
def test_produit_dune_autre_ferme_hors_de_portee(client, ferme, tomates):
    voisin = User.objects.create_user(email="voisin2@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    client.force_login(voisin)

    assert not list(client.get(reverse("vente:produits")).context["produits"])
    assert client.post(reverse("vente:produit_delete", args=[tomates.pk])).status_code == 404


@pytest.mark.django_db
def test_espace_client_ferme_accede_quand_meme_a_la_vitrine(client, ferme, tomates):
    """Un acheteur connecté ne doit pas être moins bien traité qu'un anonyme."""
    from client.models import Client as FicheClient

    _, exploitation, boutique = ferme
    acheteur = User.objects.create_user(email="acheteur@ex.com", password="pwd12345")
    FicheClient.objects.create(exploitation=exploitation, user=acheteur, nom="Dupont")
    client.force_login(acheteur)

    assert client.get(reverse("vente:marche")).status_code == 200
    assert client.get(boutique.get_absolute_url()).status_code == 200
    assert client.get(tomates.get_absolute_url()).status_code == 200


@pytest.mark.django_db
def test_boutique_creee_au_premier_enregistrement(client):
    """L'adresse publique vient du nom saisi, et ne bouge plus ensuite."""
    user = User.objects.create_user(email="nouveau@ex.com", password="pwd12345")
    # Le nom de l'exploitation n'est parfois qu'un sigle : il ne doit pas
    # décider de l'adresse de la vitrine.
    Exploitation.objects.create(owner=user, name="EARL DM")
    client.force_login(user)

    assert client.get(reverse("vente:boutique")).status_code == 200
    assert Boutique.objects.count() == 0

    client.post(reverse("vente:boutique"), {"titre": "Ma Ferme", "retrait_ferme": "1", "est_ouverte": "1"})
    boutique = Boutique.objects.get()
    assert boutique.slug == "ma-ferme" and boutique.est_ouverte is True

    # Réenregistrer sans changer d'adresse ne doit pas la suffixer.
    client.post(reverse("vente:boutique"), {"titre": "Ma Ferme", "slug": "ma-ferme", "est_ouverte": "1"})
    boutique.refresh_from_db()
    assert boutique.slug == "ma-ferme"


@pytest.mark.django_db
def test_produit_cree_depuis_le_formulaire(client, ferme):
    user, _, _ = ferme
    client.force_login(user)

    client.post(reverse("vente:produit_save"), {
        "nom": "Panier du mardi", "categorie": "legume", "unite_vente": "panier",
        "conditionnement": "1", "prix_ttc": "18,50", "taux_tva": "5,5", "visible_marche": "1",
    })

    produit = Produit.objects.get(nom="Panier du mardi")
    assert produit.prix_ttc == 18.5 and produit.slug == "panier-du-mardi"
    assert produit.visible_marche is True and produit.statut == Produit.Statut.BROUILLON


# ── Panier et commandes ─────────────────────────────────────────────

def _ajouter_au_panier(client, produit, quantite):
    return client.post(reverse("vente:panier_ajouter"), {"produit": produit.pk, "quantite": quantite})


def _valider(client, **extra):
    donnees = {"nom": "Camille Durand", "telephone": "0612345678", "mode_retrait": "ferme"}
    donnees.update(extra)
    return client.post(reverse("vente:commander"), donnees)


@pytest.mark.django_db
def test_commande_reserve_sans_sortir_le_stock(client, ferme, tomates):
    from vente.models import Commande

    _ajouter_au_panier(client, tomates, 2)
    resp = _valider(client)
    assert resp.status_code == 302

    commande = Commande.objects.get()
    assert commande.numero.endswith("-0001") and commande.montant_ttc == 24
    ligne = commande.lignes.get()
    # 2 colis de 5 kg immobilisent 10 kg, dans l'unité de l'article.
    assert ligne.quantite_stock == 10 and ligne.article == tomates.article

    tomates.article.refresh_from_db()
    assert tomates.article.quantite == 48         # le dépôt n'a pas bougé
    assert Produit.objects.get(pk=tomates.pk).disponible == 7   # 9 colis − 2 promis


@pytest.mark.django_db
def test_le_stock_ne_sort_qua_la_remise(client, ferme, tomates):
    from stock.models import Mouvement
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 2)
    _valider(client)
    commande = Commande.objects.get()

    client.force_login(user)
    client.post(reverse("vente:commande_transition", args=[commande.pk, "confirmer"]))
    tomates.article.refresh_from_db()
    assert tomates.article.quantite == 48 and Mouvement.objects.count() == 0

    client.post(reverse("vente:commande_transition", args=[commande.pk, "servir"]))
    commande.refresh_from_db()
    tomates.article.refresh_from_db()
    assert commande.statut == Commande.Statut.SERVIE and commande.servie_le is not None
    assert tomates.article.quantite == 38
    sortie = Mouvement.objects.get()
    assert sortie.motif == Mouvement.Motif.VENTE and sortie.quantite == 10
    # Servie, la commande ne réserve plus : la disponibilité ne double-compte pas.
    assert Produit.objects.get(pk=tomates.pk).disponible == 7


@pytest.mark.django_db
def test_panier_multi_fermes_donne_une_commande_par_ferme(client, ferme, tomates):
    from vente.models import Commande

    voisin = User.objects.create_user(email="voisine3@ex.com", password="pwd12345")
    autre = Exploitation.objects.create(owner=voisin, name="Ferme d'à côté")
    Boutique.objects.create(exploitation=autre, titre="Ferme d'à côté", est_ouverte=True)
    miel = Produit.objects.create(
        exploitation=autre, nom="Miel de thym", categorie=Produit.Categorie.MIEL,
        prix_ttc=8, statut=Produit.Statut.EN_LIGNE,
    )

    _ajouter_au_panier(client, tomates, 1)
    _ajouter_au_panier(client, miel, 3)
    _valider(client)

    assert Commande.objects.count() == 2
    assert {c.exploitation_id for c in Commande.objects.all()} == {tomates.exploitation_id, autre.id}
    assert Commande.objects.get(exploitation=autre).montant_ttc == 24
    assert client.session.get("panier") in (None, {})


@pytest.mark.django_db
def test_stock_pris_de_vitesse_entre_le_panier_et_la_validation(client, django_user_model, ferme, tomates):
    """Deux acheteurs remplissent leur panier ; le second est revérifié."""
    from django.test import Client as Navigateur
    from vente.models import Commande

    second = Navigateur()
    _ajouter_au_panier(client, tomates, 5)    # 9 colis dispo : les deux paniers passent
    _ajouter_au_panier(second, tomates, 5)

    _valider(client)
    assert Commande.objects.count() == 1
    assert Produit.objects.get(pk=tomates.pk).disponible == 4   # 48 kg − 25 promis

    refus = _valider(second)
    assert Commande.objects.count() == 1
    assert refus.status_code == 200
    assert "Il ne reste que" in refus.content.decode()


@pytest.mark.django_db
def test_produit_epuise_refuse_des_le_panier(client, ferme, tomates):
    _ajouter_au_panier(client, tomates, 9)
    _valider(client)

    from django.test import Client as Navigateur

    second = Navigateur()
    reponse = second.post(
        reverse("vente:panier_ajouter"), {"produit": tomates.pk, "quantite": 3}, follow=True
    )
    assert second.session.get("panier") in (None, {})
    assert "épuisé" in reponse.content.decode()


@pytest.mark.django_db
def test_coordonnees_exigees_pour_commander(client, ferme, tomates):
    from vente.models import Commande

    _ajouter_au_panier(client, tomates, 1)
    resp = client.post(reverse("vente:commander"), {"nom": "Camille", "mode_retrait": "ferme"})

    assert Commande.objects.count() == 0
    assert "email ou un t" in resp.content.decode()


@pytest.mark.django_db
def test_transition_impossible_refusee(client, ferme, tomates):
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 1)
    _valider(client)
    commande = Commande.objects.get()

    client.force_login(user)
    # « Prête » n'a pas de sens tant que la commande n'est pas confirmée.
    client.post(reverse("vente:commande_transition", args=[commande.pk, "prete"]))
    commande.refresh_from_db()
    assert commande.statut == Commande.Statut.NOUVELLE

    client.post(reverse("vente:commande_transition", args=[commande.pk, "confirmer"]))
    client.post(reverse("vente:commande_transition", args=[commande.pk, "confirmer"]))
    commande.refresh_from_db()
    assert commande.statut == Commande.Statut.CONFIRMEE and commande.confirmee_le is not None


@pytest.mark.django_db
def test_commande_annulee_libere_la_reserve(client, ferme, tomates):
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 9)
    _valider(client)
    assert Produit.objects.get(pk=tomates.pk).disponible == 0

    client.force_login(user)
    client.post(reverse("vente:commande_transition", args=[Commande.objects.get().pk, "annuler"]))
    assert Produit.objects.get(pk=tomates.pk).disponible == 9


@pytest.mark.django_db
def test_suivi_accessible_sans_compte_et_le_paysan_est_prevenu(client, ferme, tomates):
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 1)
    _valider(client)
    commande = Commande.objects.get()

    suivi = client.get(commande.get_absolute_url())
    assert suivi.status_code == 200 and commande.numero.encode() in suivi.content

    alerte = user.notifications.get()
    assert alerte.type == "commande" and commande.numero in alerte.title


@pytest.mark.django_db
def test_ecrans_commandes_du_paysan(client, ferme, tomates):
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 2)
    _valider(client)
    commande = Commande.objects.get()

    client.force_login(user)
    liste = client.get(reverse("vente:commandes"))
    assert liste.status_code == 200 and commande.numero.encode() in liste.content

    detail = client.get(reverse("vente:commande_detail", args=[commande.pk]))
    assert detail.status_code == 200
    # Une commande neuve se confirme ou se refuse, elle ne se sert pas encore.
    assert detail.context["peut"]["confirmer"] is True
    assert detail.context["peut"]["servir"] is False


@pytest.mark.django_db
def test_commande_dune_autre_ferme_hors_de_portee(client, ferme, tomates):
    from vente.models import Commande

    _ajouter_au_panier(client, tomates, 1)
    _valider(client)
    commande = Commande.objects.get()

    voisin = User.objects.create_user(email="voisin4@ex.com", password="pwd12345")
    Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    client.force_login(voisin)

    assert client.get(reverse("vente:commande_detail", args=[commande.pk])).status_code == 404
    assert client.post(reverse("vente:commande_transition", args=[commande.pk, "confirmer"])).status_code == 404
    commande.refresh_from_db()
    assert commande.statut == Commande.Statut.NOUVELLE


@pytest.mark.django_db
def test_panier_affiche_ses_lignes_et_se_met_a_jour(client, ferme, tomates):
    _ajouter_au_panier(client, tomates, 2)

    page = client.get(reverse("vente:panier"))
    assert page.status_code == 200
    contenu = page.content.decode()
    assert "Colis de tomates" in contenu and "24" in contenu

    client.post(reverse("vente:panier_ligne", args=[tomates.pk]), {"quantite": "0"})
    assert client.session.get("panier") == {}
    assert "Votre panier est vide" in client.get(reverse("vente:panier")).content.decode()


# ── Encaisser : revenu, facture, espace acheteur ────────────────────

def _servir(client, commande):
    client.post(reverse("vente:commande_transition", args=[commande.pk, "confirmer"]))
    client.post(reverse("vente:commande_transition", args=[commande.pk, "servir"]))
    commande.refresh_from_db()
    return commande


@pytest.mark.django_db
def test_la_remise_inscrit_la_vente_au_bilan(client, ferme, tomates):
    from finances.models import Revenu
    from vente.models import Commande

    user, exploitation, _ = ferme
    _ajouter_au_panier(client, tomates, 2)
    _valider(client)
    commande = Commande.objects.get()

    client.force_login(user)
    _servir(client, commande)

    revenu = Revenu.objects.get()
    assert revenu.exploitation == exploitation
    assert revenu.categorie == Revenu.Categorie.VENTE_LEGUMES
    # 24 € TTC à 5,5 % → 22,75 € HT : la TVA collectée n'est pas un revenu.
    assert revenu.montant == pytest.approx(22.75, abs=0.01)
    assert commande.numero in revenu.description


@pytest.mark.django_db
def test_facture_a_taux_mixtes(client, ferme, tomates):
    """Légumes à 5,5 % et vin à 20 % sur la même facture."""
    from vente.models import Commande

    user, exploitation, _ = ferme
    vin = Produit.objects.create(
        exploitation=exploitation, nom="Côtes du Rhône", categorie=Produit.Categorie.VIN,
        unite_vente=Produit.UniteVente.BOUTEILLE, prix_ttc=12, taux_tva=20,
        statut=Produit.Statut.EN_LIGNE,
    )
    _ajouter_au_panier(client, tomates, 1)    # 12 € TTC à 5,5 %
    _ajouter_au_panier(client, vin, 2)        # 24 € TTC à 20 %
    _valider(client)
    commande = Commande.objects.get()

    client.force_login(user)
    _servir(client, commande)
    client.post(reverse("vente:commande_facturer", args=[commande.pk]))

    commande.refresh_from_db()
    facture = commande.facture
    assert facture is not None and facture.numero.startswith("F-")
    taux = {ligne["taux_tva"] for ligne in facture.lignes}
    assert taux == {5.5, 20.0}
    # Chaque ligne porte son taux : la TVA totale n'est pas un taux moyen.
    assert facture.montant_tva == pytest.approx(12 * 0.055 / 1.055 + 24 * 0.20 / 1.20, abs=0.05)
    assert facture.montant_ttc == pytest.approx(36, abs=0.05)
    # Le champ document ne retient que le taux dominant (ici le vin).
    assert facture.taux_tva == 20


@pytest.mark.django_db
def test_facturation_cree_la_fiche_client_de_lacheteur(client, ferme, tomates):
    from client.models import Client as FicheClient
    from vente.models import Commande

    user, exploitation, _ = ferme
    _ajouter_au_panier(client, tomates, 1)
    _valider(client, nom="Camille Durand", email="camille@exemple.fr")
    commande = Commande.objects.get()
    assert commande.client_ref is None      # un acheteur anonyme n'a pas de fiche

    client.force_login(user)
    _servir(client, commande)
    client.post(reverse("vente:commande_facturer", args=[commande.pk]))

    fiche = FicheClient.objects.get(exploitation=exploitation)
    assert fiche.nom == "Camille Durand" and fiche.email == "camille@exemple.fr"
    assert fiche.categorie == FicheClient.Categorie.PARTICULIER
    commande.refresh_from_db()
    assert commande.client_ref == fiche
    # Réglée au retrait : la facture ne fait que constater.
    assert commande.facture.statut == commande.facture.Statut.PAYEE


@pytest.mark.django_db
def test_facture_refusee_avant_la_remise_et_en_double(client, ferme, tomates):
    from finances.models import Facture
    from vente.models import Commande

    user, _, _ = ferme
    _ajouter_au_panier(client, tomates, 1)
    _valider(client)
    commande = Commande.objects.get()
    client.force_login(user)

    client.post(reverse("vente:commande_facturer", args=[commande.pk]))
    assert Facture.objects.count() == 0     # rien n'est encore remis

    _servir(client, commande)
    client.post(reverse("vente:commande_facturer", args=[commande.pk]))
    client.post(reverse("vente:commande_facturer", args=[commande.pk]))
    assert Facture.objects.count() == 1     # et pas deux


@pytest.mark.django_db
def test_facture_dun_professionnel_reste_due(client, ferme, tomates):
    from client.models import Client as FicheClient
    from vente.models import Commande

    user, exploitation, _ = ferme
    acheteur = User.objects.create_user(email="resto@ex.com", password="pwd12345")
    FicheClient.objects.create(
        exploitation=exploitation, user=acheteur, nom="Le Bistrot",
        categorie=FicheClient.Categorie.PROFESSIONNEL,
    )
    client.force_login(acheteur)
    _ajouter_au_panier(client, tomates, 2)
    _valider(client, nom="Le Bistrot", email="resto@ex.com")
    commande = Commande.objects.get()
    assert commande.client_ref is not None   # rattachée à sa fiche dès la commande

    paysan = client.__class__()
    paysan.force_login(user)
    _servir(paysan, commande)
    paysan.post(reverse("vente:commande_facturer", args=[commande.pk]))

    commande.refresh_from_db()
    assert commande.facture.statut == commande.facture.Statut.EN_ATTENTE
    assert commande.facture.superpdp_envoyee is False


@pytest.mark.django_db
def test_lacheteur_retrouve_ses_commandes_dans_son_espace(client, ferme, tomates):
    from client.models import Client as FicheClient
    from vente.models import Commande

    _, exploitation, _ = ferme
    acheteur = User.objects.create_user(email="fidele@ex.com", password="pwd12345")
    FicheClient.objects.create(exploitation=exploitation, user=acheteur, nom="Durand")
    client.force_login(acheteur)
    _ajouter_au_panier(client, tomates, 1)
    _valider(client, nom="Durand")

    page = client.get(reverse("vente:mes_commandes"))
    assert page.status_code == 200
    assert Commande.objects.get().numero.encode() in page.content


@pytest.mark.django_db
def test_numerotation_partagee_avec_la_facturation_classique(client, ferme, tomates):
    """Les factures de vente directe suivent la même série que les autres."""
    from django.utils import timezone

    from finances.models import Facture
    from vente.models import Commande

    user, exploitation, _ = ferme
    annee = timezone.localdate().year
    Facture.objects.create(
        exploitation=exploitation, numero=f"F-{annee}-001", date_emission=timezone.now(),
        client_nom="Client historique", montant_ht=100, montant_ttc=120,
    )

    _ajouter_au_panier(client, tomates, 1)
    _valider(client)
    commande = Commande.objects.get()
    client.force_login(user)
    _servir(client, commande)
    client.post(reverse("vente:commande_facturer", args=[commande.pk]))

    commande.refresh_from_db()
    assert commande.facture.numero == f"F-{annee}-002"


@pytest.mark.django_db
def test_le_marche_suit_la_convention_nos_terroirs(client):
    """Le marché et la vitrine des producteurs sont la même place de marché.

    Elle ne change donc pas de visage entre les deux : même bandeau jaune,
    mêmes atomes, et le panier en plus là où l'on achète.
    """
    page = client.get("/marche/").content.decode()
    assert 'class="nt-bandeau"' in page
    assert 'class="lp-header"' not in page, "l'ancien bandeau turquoise persiste"
    assert "background: var(--nt-jaune); color: var(--nt-noir);" in page
    # Le panier n'apparaît que sur les pages où l'on achète.
    assert 'href="/panier/"' in page
    assert "hs-btn-primary" not in page and "hs-chip-btn" not in page
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_le_bandeau_ne_porte_le_panier_que_sur_les_pages_d_achat(client):
    """La vitrine des producteurs présente les fermes ; on achète sur le marché.

    Le pied de page, lui, sert de sommaire et peut mener au panier depuis
    n'importe où : c'est le bandeau qui est contextuel.
    """
    import re

    def bandeau(url):
        corps = client.get(url).content.decode()
        m = re.search(r'<header class="nt-bandeau".*?</header>', corps, re.S)
        assert m, f"pas de bandeau sur {url}"
        return m.group(0)

    assert 'href="/panier/"' not in bandeau("/nos-terroirs/")
    assert 'href="/panier/"' in bandeau("/marche/")


@pytest.mark.django_db
def test_le_marche_offre_toutes_les_categories(client, django_user_model):
    """Toutes, y compris les vides.

    Un filtre absent laisse croire que la catégorie n'existe pas, quand elle
    est seulement sans offre aujourd'hui. Les vides sont montrées en retrait.
    """
    from django.utils.text import slugify

    from exploitations.models import Exploitation
    from vente.models import Boutique, Produit

    u = django_user_model.objects.create_user(email="cat@ex.com", password="pwd12345")
    e = Exploitation.objects.create(owner=u, name="Ferme Test")
    Boutique.objects.create(exploitation=e, slug="ferme-test", est_ouverte=True, visible_marche=True)
    for nom, cat in [("Pommes", "fruit"), ("Lentilles", "legumineuse"), ("Huîtres", "poisson")]:
        Produit.objects.create(exploitation=e, nom=nom, slug=slugify(nom), categorie=cat,
                               prix_ttc=3, statut=Produit.Statut.EN_LIGNE, visible_marche=True)

    reponse = client.get("/marche/")
    familles = {f["cle"]: f["n"] for f in reponse.context["familles"]}
    assert len(familles) == len(Produit.Categorie.choices)
    assert familles["fruit"] == 1 and familles["legumineuse"] == 1 and familles["poisson"] == 1
    assert familles["fleur"] == 0  # présente et vide
    assert "nt-chip-vide" in reponse.content.decode()

    # Chaque catégorie filtre ce qu'elle annonce.
    assert [p.nom for p in client.get("/marche/poisson/").context["produits"]] == ["Huîtres"]
    # Une clé inconnue retombe sur le marché entier plutôt que sur du vide.
    assert len(client.get("/marche/zzz/").context["produits"]) == 3


@pytest.mark.django_db
def test_les_categories_ajoutees_existent(client):
    """Légumineuses et poissons manquaient au catalogue."""
    from vente.models import Produit

    valeurs = Produit.Categorie.values
    assert "legumineuse" in valeurs and "poisson" in valeurs
