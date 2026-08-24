"""Tests finances : charges/revenus, bilan ROI, factures TVA, exports, intents IA."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from exploitations.models import Exploitation
from finances.models import Charge, Facture, Revenu
from finances.services import compute_bilan
from parcelles.models import Parcelle

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="fi@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Fi", total_area=10)
    return user, exploitation


@pytest.mark.django_db
def test_bilan_roi_computation(setup):
    user, exploitation = setup
    Parcelle.objects.create(exploitation=exploitation, name="A", area=5)
    Revenu.objects.create(exploitation=exploitation, date=timezone.now(), categorie="vente_fruits", montant=10000)
    Charge.objects.create(exploitation=exploitation, date=timezone.now(), categorie="engrais", montant=3000)
    bilan = compute_bilan(exploitation)
    assert bilan.total_revenus == 10000 and bilan.total_charges == 3000
    assert bilan.resultat_net == 7000 and bilan.marge_par_ha == 1400  # 7000 / 5 ha


@pytest.mark.django_db
def test_facture_tva_computed(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.post(
        "/api/factures/",
        {"numero": "FAC-2026-001", "date_emission": "2026-06-23T00:00:00Z", "montant_ht": 1000, "taux_tva": 20},
        content_type="application/json",
    )
    assert resp.status_code == 201
    facture = Facture.objects.get(numero="FAC-2026-001")
    assert facture.montant_tva == 200 and facture.montant_ttc == 1200


@pytest.mark.django_db
def test_csv_export(client, setup):
    user, exploitation = setup
    Charge.objects.create(exploitation=exploitation, date=timezone.now(), categorie="eau", montant=500, fournisseur="Régie")
    client.force_login(user)
    resp = client.get("/reports/csv/?type=charges")
    assert resp.status_code == 200 and resp["Content-Type"] == "text/csv"
    body = resp.content.decode()
    assert "categorie" in body and "Régie" in body


@pytest.mark.django_db
def test_pdf_export(client, setup):
    user, exploitation = setup
    client.force_login(user)
    resp = client.get("/reports/pdf/?type=taxonomie_verte&year=2026")
    # 200 + PDF si WeasyPrint dispo, sinon 501 (dépend des libs système)
    assert resp.status_code in (200, 501)
    if resp.status_code == 200:
        assert resp["Content-Type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_ai_intent_creates_charge_and_revenu(setup, monkeypatch):
    from ia import services

    user, exploitation = setup
    monkeypatch.setattr(services.llm, "is_configured", lambda: True)

    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda m, **k: {"response": "Charge notée", "intent": "creer_charge", "needs_more_info": False,
                        "data": {"categorie": "engrais", "montant": 150, "fournisseur": "Yara"}},
    )
    r1 = services.execute_intent(exploitation, user, "Note une charge engrais de 150€ chez Yara")
    assert r1["entity"]["type"] == "charge"
    assert Charge.objects.filter(exploitation=exploitation, montant=150).exists()

    monkeypatch.setattr(
        services.llm, "generate_json",
        lambda m, **k: {"response": "Vente notée", "intent": "creer_revenu", "needs_more_info": False,
                        "data": {"categorie": "vente_fruits", "montant": 2000, "acheteur": "Coop"}},
    )
    r2 = services.execute_intent(exploitation, user, "Vente de fruits 2000€ à la coop")
    assert r2["entity"]["type"] == "revenu"
    assert Revenu.objects.filter(exploitation=exploitation, montant=2000).exists()


# ── Facturation électronique (SUPER PDP) ────────────────────────────
#
# La génération UBL est testée hors ligne : c'est elle qui porte les règles
# métier (mentions légales, totaux, identifiants). Les appels réseau, eux, sont
# éprouvés par le validateur de la plateforme, pas par des tests unitaires qui
# ne feraient que rejouer nos propres suppositions.

from finances import superpdp, ubl
from client.models import Client as FicheClient


@pytest.fixture
def facture_client(setup):
    _, exploitation = setup
    client = FicheClient.objects.create(
        exploitation=exploitation, nom="Tricatel", siret="00000000100014",
        voie="1 rue du Bouillon", ville="Paris", code_postal="75001",
        superpdp_adresse="0225:315143296_68152",
    )
    facture = Facture.objects.create(
        exploitation=exploitation, numero="F-2026-001", client_ref=client, client_nom=client.nom,
        date_emission=timezone.now(),
        lignes=[
            {"designation": "Blé tendre", "quantite": 10, "prix_unitaire": 200, "unite": "TNE", "taux_tva": 5.5},
            {"designation": "Battage", "quantite": 1, "prix_unitaire": 800, "taux_tva": 20},
        ],
        montant_ht=2800, taux_tva=20,
    )
    return facture


VENDEUR = {"formal_name": "Ferme Fi", "number": "000000002", "city": "Millau", "country": "FR"}


def _ubl(facture):
    return ubl.construire(
        facture, vendeur=VENDEUR,
        endpoint_vendeur="0225:315143296_68153",
        endpoint_client="0225:315143296_68152",
    )


@pytest.mark.django_db
def test_ubl_porte_les_mentions_legales_obligatoires(facture_client):
    """BR-FR-05 : sans ces trois mentions, la facture est retoquée."""
    xml = _ubl(facture_client)
    for code, _texte in ubl.MENTIONS_LEGALES:
        assert f"#{code}#" in xml


@pytest.mark.django_db
def test_ubl_totaux_recalcules_depuis_les_lignes(facture_client):
    """Le validateur vérifie l'arithmétique : on recalcule, on ne recopie pas."""
    xml = _ubl(facture_client)
    # 10 × 200 à 5,5 % + 1 × 800 à 20 % = 2800 HT, 270 de TVA, 3070 TTC
    assert "<cbc:TaxExclusiveAmount currencyID=\"EUR\">2800.00</cbc:TaxExclusiveAmount>" in xml
    assert "<cbc:PayableAmount currencyID=\"EUR\">3070.00</cbc:PayableAmount>" in xml
    ht, tva = ubl.totaux_lignes(facture_client)
    assert (float(ht), float(tva)) == (2800.0, 270.0)


@pytest.mark.django_db
def test_ubl_un_sous_total_par_taux_de_tva(facture_client):
    xml = _ubl(facture_client)
    assert xml.count("<cac:TaxSubtotal>") == 2
    assert "<cbc:Percent>5.5</cbc:Percent>" in xml and "<cbc:Percent>20.0</cbc:Percent>" in xml


@pytest.mark.django_db
def test_ubl_refuse_un_client_sans_adresse_electronique(facture_client):
    """Sans identifiant d'annuaire, la facture ne peut pas être routée."""
    with pytest.raises(ubl.FactureIncomplete):
        ubl.construire(facture_client, vendeur=VENDEUR, endpoint_vendeur="0225:x", endpoint_client="")


@pytest.mark.django_db
def test_ubl_facture_sans_ligne_retombe_sur_le_montant_ht(setup):
    _, exploitation = setup
    client = FicheClient.objects.create(exploitation=exploitation, nom="Tricatel",
                                          superpdp_adresse="0225:315143296_68152")
    facture = Facture.objects.create(
        exploitation=exploitation, numero="F-2026-002", client_ref=client, client_nom=client.nom,
        date_emission=timezone.now(), lignes=[], montant_ht=1000, taux_tva=20,
    )
    xml = _ubl(facture)
    assert xml.count("<cac:InvoiceLine>") == 1
    assert "<cbc:PayableAmount currencyID=\"EUR\">1200.00</cbc:PayableAmount>" in xml


def test_tva_intracommunautaire_deduite_du_siren():
    """Clé = (12 + 3 × (SIREN mod 97)) mod 97.

    Références : la facture d'exemple de SUPER PDP, qui porte FR18000000002
    pour le SIREN 000000002 et FR15000000001 pour 000000001.
    """
    assert ubl.cle_tva_francaise("000000002") == "FR18000000002"
    assert ubl.cle_tva_francaise("000000001") == "FR15000000001"
    # Un SIRET (14 chiffres) est accepté : seuls les 9 premiers comptent.
    assert ubl.cle_tva_francaise("00000000200015") == "FR18000000002"
    assert ubl.cle_tva_francaise("") == ""


def test_client_inerte_sans_identifiants(settings):
    """Sans clés, aucun appel réseau : on lève une erreur explicite."""
    settings.SUPERPDP_CLIENT_ID = ""
    settings.SUPERPDP_CLIENT_SECRET = ""
    assert superpdp.is_configured() is False
    with pytest.raises(superpdp.SuperPDPNotConfigured):
        superpdp.token()


# ── Devis ───────────────────────────────────────────────────────────
#
# Le devis partage l'éditeur de la facture mais reste un document distinct :
# il ne part jamais sur le réseau de facturation électronique.

from finances.models import Devis


@pytest.mark.django_db
def test_devis_accepte_se_convertit_en_facture(client, setup):
    user, exploitation = setup
    client.force_login(user)
    cl = FicheClient.objects.create(exploitation=exploitation, nom="Tricatel")
    devis = Devis.objects.create(
        exploitation=exploitation, numero="D-2026-001", client_ref=cl, client_nom=cl.nom,
        date_emission=timezone.now(), statut=Devis.Statut.ACCEPTE,
        lignes=[{"designation": "Semis", "quantite": 2, "prix_unitaire": 100, "taux_tva": 20}],
        montant_ht=200, montant_tva=40, montant_ttc=240,
    )
    resp = client.post(f"/devis/{devis.pk}/convertir/")
    assert resp.status_code == 302
    devis.refresh_from_db()
    facture = devis.facture
    assert facture.montant_ttc == 240 and facture.lignes == devis.lignes
    assert facture.numero.startswith("F-")
    # Une deuxième conversion est refusée : le devis est déjà facturé.
    assert devis.convertible is False
    client.post(f"/devis/{devis.pk}/convertir/")
    assert Facture.objects.filter(devis=devis).count() == 1


@pytest.mark.django_db
def test_devis_non_accepte_ne_se_convertit_pas(client, setup):
    user, exploitation = setup
    client.force_login(user)
    devis = Devis.objects.create(
        exploitation=exploitation, numero="D-2026-002", client_nom="Tricatel",
        date_emission=timezone.now(), statut=Devis.Statut.ENVOYE,
    )
    client.post(f"/devis/{devis.pk}/convertir/")
    assert Facture.objects.filter(devis=devis).count() == 0


@pytest.mark.django_db
def test_devis_expire_quand_sa_validite_est_depassee(setup):
    _, exploitation = setup
    devis = Devis.objects.create(
        exploitation=exploitation, numero="D-2026-003", client_nom="Tricatel",
        date_emission=timezone.now() - timedelta(days=60),
        date_validite=timezone.now() - timedelta(days=30),
        statut=Devis.Statut.ENVOYE,
    )
    assert devis.est_expire is True
    # Un devis déjà accepté ne « expire » pas : la réponse du client fait foi.
    devis.statut = Devis.Statut.ACCEPTE
    assert devis.est_expire is False


@pytest.mark.django_db
def test_les_series_de_numerotation_sont_independantes(client, setup):
    """F-2026-001 et D-2026-001 coexistent : deux séries, deux compteurs."""
    from finances.views import _prochain_numero

    user, exploitation = setup
    annee = timezone.localdate().year
    Facture.objects.create(exploitation=exploitation, numero=f"F-{annee}-001",
                           client_nom="X", date_emission=timezone.now())
    Devis.objects.create(exploitation=exploitation, numero=f"D-{annee}-001",
                         client_nom="X", date_emission=timezone.now())
    assert _prochain_numero(exploitation) == f"F-{annee}-002"
    assert _prochain_numero(exploitation, Devis, "D") == f"D-{annee}-002"
