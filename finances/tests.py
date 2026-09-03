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
def test_devis_signe_se_convertit_en_facture(client, setup):
    user, exploitation = setup
    client.force_login(user)
    cl = FicheClient.objects.create(exploitation=exploitation, nom="Tricatel")
    devis = Devis.objects.create(
        exploitation=exploitation, numero="D-2026-001", client_ref=cl, client_nom=cl.nom,
        date_emission=timezone.now(), statut=Devis.Statut.ACCEPTE,
        lignes=[{"designation": "Semis", "quantite": 2, "prix_unitaire": 100, "taux_tva": 20}],
        montant_ht=200, montant_tva=40, montant_ttc=240,
        signature_url="data:image/png;base64,iVBORw0KGgo=", signature_nom="M. Tricatel",
        signature_mention="Bon pour accord", signature_date=timezone.now(),
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
def test_devis_non_signe_ne_se_convertit_pas(client, setup):
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


# ── Signature du devis ──────────────────────────────────────────────
#
# Un devis n'engage qu'une fois signé de la main du client sous la mention
# « Bon pour accord ». Tant qu'elle manque, il n'y a rien à facturer.

SIGNATURE = "data:image/png;base64,iVBORw0KGgo="


def _signer(client, devis, mention="Bon pour accord", nom="M. Tricatel", signature=SIGNATURE):
    return client.post(f"/devis/{devis.pk}/signature/", {
        "signature_url": signature, "signature_nom": nom, "signature_mention": mention,
    })


@pytest.fixture
def devis_a_signer(setup):
    _, exploitation = setup
    fiche = FicheClient.objects.create(exploitation=exploitation, nom="Tricatel")
    return Devis.objects.create(
        exploitation=exploitation, numero="D-2026-100", client_ref=fiche, client_nom=fiche.nom,
        date_emission=timezone.now(), statut=Devis.Statut.ENVOYE,
        lignes=[{"designation": "Taille", "quantite": 4, "prix_unitaire": 150, "taux_tva": 20}],
        montant_ht=600, montant_tva=120, montant_ttc=720,
    )


@pytest.mark.django_db
def test_un_devis_non_signe_ne_se_facture_pas(client, setup, devis_a_signer):
    user, _ = setup
    client.force_login(user)
    assert devis_a_signer.convertible is False
    client.post(f"/devis/{devis_a_signer.pk}/convertir/")
    assert Facture.objects.filter(devis=devis_a_signer).count() == 0


@pytest.mark.django_db
def test_la_mention_doit_etre_recopiee(client, setup, devis_a_signer):
    """« Ok pour moi » n'engage pas : la mention légale est attendue."""
    user, _ = setup
    client.force_login(user)
    _signer(client, devis_a_signer, mention="ok pour moi")
    devis_a_signer.refresh_from_db()
    assert devis_a_signer.est_signe is False


@pytest.mark.django_db
def test_la_mention_tolere_casse_accents_et_espaces(client, setup, devis_a_signer):
    """Le client l'écrit à la main : on compare le sens, pas les caractères."""
    user, _ = setup
    client.force_login(user)
    _signer(client, devis_a_signer, mention="  BON  pour Accord ")
    devis_a_signer.refresh_from_db()
    assert devis_a_signer.est_signe is True


@pytest.mark.django_db
def test_signature_sans_trace_refusee(client, setup, devis_a_signer):
    user, _ = setup
    client.force_login(user)
    _signer(client, devis_a_signer, signature="")
    devis_a_signer.refresh_from_db()
    assert devis_a_signer.est_signe is False


@pytest.mark.django_db
def test_le_devis_signe_vaut_accepte_et_se_facture(client, setup, devis_a_signer):
    user, _ = setup
    client.force_login(user)
    _signer(client, devis_a_signer)
    devis_a_signer.refresh_from_db()
    assert devis_a_signer.statut == Devis.Statut.ACCEPTE
    assert devis_a_signer.signature_date is not None
    client.post(f"/devis/{devis_a_signer.pk}/convertir/")
    devis_a_signer.refresh_from_db()
    assert devis_a_signer.facture.montant_ttc == 720


@pytest.mark.django_db
def test_un_devis_signe_n_expire_pas(setup, devis_a_signer):
    """La signature fige l'accord : la date de validité ne le défait pas."""
    devis_a_signer.date_validite = timezone.now() - timedelta(days=1)
    devis_a_signer.signature_url = SIGNATURE
    devis_a_signer.signature_nom = "M. Tricatel"
    devis_a_signer.signature_mention = "Bon pour accord"
    devis_a_signer.signature_date = timezone.now()
    assert devis_a_signer.est_expire is False


# ── Bibliothèque de logos ───────────────────────────────────────────


@pytest.fixture
def ferme_logo(db, django_user_model):
    from exploitations.models import Exploitation

    u = django_user_model.objects.create_user(email="biblio@ex.com", password="pwd12345")
    return u, Exploitation.objects.create(owner=u, name="Ferme Biblio")


def _png(nom="marque.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    # En-tête PNG valide : suffisant pour ImageField, qui vérifie l'image.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 255, 255)).save(buf, "PNG")
    return SimpleUploadedFile(nom, buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_le_premier_logo_devient_le_defaut(client, ferme_logo):
    """Une bibliothèque pleine dont aucun n'est désigné ne sert à rien."""
    from finances.models import Logo

    user, exploitation = ferme_logo
    client.force_login(user)
    assert client.post("/logos/ajouter/", {"fichier": _png()}).status_code == 302

    logo = Logo.objects.get(exploitation=exploitation)
    assert logo.par_defaut is True
    # Sans nom donné, celui du fichier fait l'affaire.
    assert logo.nom == "marque"


@pytest.mark.django_db
def test_un_seul_logo_par_defaut_a_la_fois(client, ferme_logo):
    from finances.models import Logo

    user, exploitation = ferme_logo
    client.force_login(user)
    client.post("/logos/ajouter/", {"fichier": _png("un.png")})
    client.post("/logos/ajouter/", {"fichier": _png("deux.png"), "par_defaut": "on"})

    defauts = list(Logo.objects.filter(exploitation=exploitation, par_defaut=True))
    assert len(defauts) == 1 and defauts[0].nom == "deux"


@pytest.mark.django_db
def test_renommer_et_remplacer_un_logo(client, ferme_logo):
    from finances.models import Logo

    user, exploitation = ferme_logo
    client.force_login(user)
    client.post("/logos/ajouter/", {"fichier": _png("avant.png")})
    logo = Logo.objects.get(exploitation=exploitation)

    client.post(f"/logos/{logo.pk}/modifier/", {"nom": "Marque de la ferme"})
    logo.refresh_from_db()
    assert logo.nom == "Marque de la ferme"

    client.post(f"/logos/{logo.pk}/modifier/", {"nom": logo.nom, "fichier": _png("apres.png")})
    logo.refresh_from_db()
    assert "apres" in logo.fichier.name


@pytest.mark.django_db
def test_supprimer_le_defaut_en_designe_un_autre(client, ferme_logo):
    """La bibliothèque ne doit jamais rester sans référence."""
    from finances.models import Logo

    user, exploitation = ferme_logo
    client.force_login(user)
    client.post("/logos/ajouter/", {"fichier": _png("un.png")})
    client.post("/logos/ajouter/", {"fichier": _png("deux.png")})
    defaut = Logo.objects.get(exploitation=exploitation, par_defaut=True)

    client.post(f"/logos/{defaut.pk}/supprimer/")
    restants = Logo.objects.filter(exploitation=exploitation)
    assert restants.count() == 1
    assert restants.first().par_defaut is True


@pytest.mark.django_db
def test_le_logo_est_filtre_sur_le_format(client, ferme_logo):
    """Un document à valeur légale n'embarque pas n'importe quel fichier."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from finances.models import Logo

    user, _exploitation = ferme_logo
    client.force_login(user)
    client.post("/logos/ajouter/", {
        "fichier": SimpleUploadedFile("doc.pdf", b"%PDF-1.4", content_type="application/pdf")})
    assert Logo.objects.count() == 0


@pytest.mark.django_db
def test_l_editeur_puise_dans_la_bibliotheque(client, ferme_logo):
    """Il ne téléverse plus : la même marque doit servir la facture suivante."""
    user, _exploitation = ferme_logo
    client.force_login(user)
    client.post("/logos/ajouter/", {"fichier": _png("marque.png")})

    page = client.get("/facturation/nouvelle/").content.decode()
    assert 'name="logo"' in page and "<select" in page
    assert 'type="file" name="logo"' not in page, "le téléversement persiste dans l'éditeur"
    assert "{#" not in page and "{{" not in page


@pytest.mark.django_db
def test_le_logo_du_document_l_emporte_sur_le_defaut(ferme_logo):
    """Un devis signé sous une marque ne peut pas s'afficher sous une autre."""
    from finances.models import Devis, Logo
    from finances.views import _emetteur

    _user, exploitation = ferme_logo
    defaut = Logo.objects.create(exploitation=exploitation, fichier=_png("defaut.png"),
                                 par_defaut=True)
    autre = Logo.objects.create(exploitation=exploitation, fichier=_png("autre.png"))

    from django.utils import timezone

    devis = Devis.objects.create(exploitation=exploitation, numero="D-1",
                                 client_nom="Client", date_emission=timezone.now(),
                                 logo=autre)
    assert _emetteur(exploitation, devis)["logo_url"] == autre.fichier.url
    # Sans logo propre, le document suit la marque courante.
    devis.logo = None
    assert _emetteur(exploitation, devis)["logo_url"] == defaut.fichier.url


# ── Identité de facturation ─────────────────────────────────────────


@pytest.mark.django_db
def test_l_identite_ne_recopie_pas_ce_qui_existe_ailleurs(client, ferme_logo):
    """Raison sociale, SIRET, TVA et adresse ont déjà leur page.

    Les ressaisir ici serait le meilleur moyen qu'ils divergent, et sur une
    facture cela vaut un numéro ou une adresse faux.
    """
    from finances.models import IdentiteFacturation

    user, exploitation = ferme_logo
    client.force_login(user)
    page = client.get("/facturation/coordonnees/").content.decode()

    assert "Identité de facturation" in page
    # Montrées, avec le chemin pour les corriger — jamais en champ de saisie.
    for lu in ("SIRET", "TVA intracommunautaire", "Raison sociale"):
        assert lu in page
    for champ in ('name="siret"', 'name="raison_sociale"', 'name="tva_intra"', 'name="adresse"'):
        assert champ not in page, f"{champ} ne doit pas se ressaisir ici"
    assert "{#" not in page and "{{" not in page

    # La fiche se crée à la première visite plutôt qu'à l'enregistrement.
    assert IdentiteFacturation.objects.filter(exploitation=exploitation).exists()


@pytest.mark.django_db
def test_les_coordonnees_de_paiement_s_enregistrent(client, ferme_logo):
    from finances.models import IdentiteFacturation

    user, exploitation = ferme_logo
    client.force_login(user)
    reponse = client.post("/facturation/coordonnees/", {
        "banque": "Crédit Agricole",
        "iban": "FR76 1234 5678 9012 3456 7890 123",
        "bic": "AGRIFRPP",
        "conditions_reglement": "30 jours fin de mois",
        "capital_social": "7 500",
        "rcs": "RCS Digne-les-Bains 123 456 789",
        "mentions": "Indemnité forfaitaire de recouvrement de 40 €.",
    })
    assert reponse.status_code == 302

    identite = IdentiteFacturation.objects.get(exploitation=exploitation)
    # L'IBAN se range sans espaces et en majuscules, se relit par quatre.
    assert identite.iban == "FR761234567890123456789 0123".replace(" ", "")
    assert identite.iban_lisible.startswith("FR76 1234 5678")
    assert identite.capital_social == 7500
    assert identite.peut_encaisser is True


@pytest.mark.django_db
def test_l_emetteur_lit_les_sources_et_non_le_miroir(ferme_logo):
    """Le miroir posé sur l'exploitation peut avoir divergé.

    Cas réel rencontré ailleurs : `Exploitation.city` disait une commune, et
    l'adresse enregistrée une autre. Sur une facture, c'est une adresse fausse.
    """
    from exploitations.models import AdresseExploitation, EntrepriseLiee
    from finances.views import _emetteur

    _user, exploitation = ferme_logo
    exploitation.raison_sociale = "Miroir SARL"
    exploitation.city = "Digne-les-Bains"
    exploitation.siret = "00000000000000"
    exploitation.save()

    EntrepriseLiee.objects.create(exploitation=exploitation, raison_sociale="Vraie SARL",
                                  siret="90100075200021", principale=True)
    AdresseExploitation.objects.create(exploitation=exploitation, voie_numero="3",
                                       voie_type="rue", voie_nom="Dubreuil",
                                       city="Montpellier", postal_code="34090",
                                       principale=True)

    bloc = _emetteur(exploitation)
    assert bloc["nom"] == "Vraie SARL"
    assert bloc["siret"] == "90100075200021"
    assert "Montpellier" in bloc["commune"] and "34090" in bloc["commune"]
    assert "Dubreuil" in bloc["adresse"]


@pytest.mark.parametrize("saisi,attendu", [
    ("12,50", 12.5),
    ("12.50", 12.5),
    ("7 500", 7500.0),          # espace ordinaire
    ("7 500", 7500.0),     # insécable
    ("7 500", 7500.0),     # insécable étroite, produite par le formatage FR
    ("1 234,56 €", 1234.56),
    ("", None), (None, None), ("abc", None),
])
def test_un_montant_saisi_avec_ses_separateurs_est_lu(saisi, attendu):
    """« 7 500 » se perdait sans un mot : le champ repartait vide."""
    from finances.views import _to_float

    assert _to_float(saisi) == attendu
