"""Tests contrat : assurances — statut, échéances, documents, lecture IA."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from contrat.models import Assurance, DocumentAssurance
from exploitations.models import Exploitation

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="assur@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme Assurée")
    return user, exploitation


def _police(**surcharges):
    champs = {
        "intitule": "Multirisque exploitation",
        "type_assurance": "multirisque",
        "statut": "active",
        "assureur": "Groupama",
        "numero_police": "MR-2026-0042",
        "prime_annuelle": "2 450,00",
        "capital_assure": "350000",
        "plafond": "500000",
        "date_debut": "2026-01-01",
        "date_fin": "2026-12-31",
        "franchise": "10 % avec un minimum de 500 €",
        "delai_declaration_jours": "5",
        "telephone_sinistre": "0800123456",
        "email_sinistre": "sinistre@groupama.fr",
        "procedure_sinistre": "Appeler le 0800, puis envoyer les photos sous 48 h.",
        "garanties": "Incendie, tempête, dégât des eaux, RC exploitation.",
        "exclusions": "Défaut d'entretien, faute intentionnelle.",
        "courtier": "Agence de Carpentras",
        "telephone_courtier": "0490000000",
        "preavis_resiliation_jours": "60",
        "tacite_reconduction": "on",
    }
    champs.update(surcharges)
    return champs


@pytest.mark.django_db
def test_enregistrer_une_police_avec_ses_conditions(client, setup):
    """Ce qui sert le jour du sinistre est enregistré, pas noyé dans les notes."""
    user, exploitation = setup
    client.force_login(user)
    assert client.post("/assurances/nouvelle/", _police()).status_code == 302

    a = Assurance.objects.get(exploitation=exploitation)
    assert a.assureur == "Groupama" and a.prime_annuelle == 2450.0
    assert a.franchise == "10 % avec un minimum de 500 €"
    assert a.delai_declaration_jours == 5
    assert a.telephone_sinistre == "0800123456"
    assert a.preavis_resiliation_jours == 60 and a.tacite_reconduction is True
    assert a.plafond == 500000


@pytest.mark.django_db
def test_actif_expire_ou_resilie(setup):
    _user, exploitation = setup
    aujourdhui = timezone.localdate()

    en_cours = Assurance.objects.create(
        exploitation=exploitation, intitule="En cours", statut="active",
        date_fin=aujourdhui + timedelta(days=200))
    proche = Assurance.objects.create(
        exploitation=exploitation, intitule="Bientôt", statut="active",
        date_fin=aujourdhui + timedelta(days=30))
    passee = Assurance.objects.create(
        exploitation=exploitation, intitule="Passée", statut="active",
        date_fin=aujourdhui - timedelta(days=1))
    resiliee = Assurance.objects.create(
        exploitation=exploitation, intitule="Résiliée", statut="resiliee",
        date_fin=aujourdhui + timedelta(days=200))

    assert en_cours.est_en_vigueur and not en_cours.echeance_proche
    # Le préavis courant étant de deux mois, l'alerte s'allume à soixante jours.
    assert proche.est_en_vigueur and proche.echeance_proche
    assert not passee.est_en_vigueur
    assert not resiliee.est_en_vigueur and not resiliee.echeance_proche
    assert en_cours.jours_avant_echeance == 200


@pytest.mark.django_db
def test_les_echeances_proches_remontent_sur_la_page(client, setup):
    user, exploitation = setup
    Assurance.objects.create(
        exploitation=exploitation, intitule="Grêle 2026", statut="active",
        date_fin=timezone.localdate() + timedelta(days=20))
    client.force_login(user)
    resp = client.get("/assurances/")
    assert [a.intitule for a in resp.context["echeances_proches"]] == ["Grêle 2026"]
    html = resp.content.decode()
    assert "arrive à échéance" in html
    assert "{#" not in html and "{{" not in html


@pytest.mark.django_db
def test_joindre_un_document_scanne(client, setup):
    user, exploitation = setup
    a = Assurance.objects.create(exploitation=exploitation, intitule="Multirisque")
    client.force_login(user)

    resp = client.post(f"/assurances/{a.pk}/document/", {
        "document": SimpleUploadedFile("police.pdf", b"%PDF-1.4 ...", content_type="application/pdf"),
        "type_document": "police"})
    assert resp.status_code == 302
    d = DocumentAssurance.objects.get(assurance=a)
    assert d.type_document == "police" and d.nom == "police.pdf"


@pytest.mark.django_db
def test_le_document_est_filtre_sur_le_format_et_la_taille(client, setup):
    from contrat.views import TAILLE_MAX_DOC

    user, exploitation = setup
    a = Assurance.objects.create(exploitation=exploitation, intitule="Multirisque")
    client.force_login(user)

    client.post(f"/assurances/{a.pk}/document/", {
        "document": SimpleUploadedFile("police.exe", b"MZ", content_type="application/octet-stream")})
    client.post(f"/assurances/{a.pk}/document/", {
        "document": SimpleUploadedFile("police.pdf", b"x" * (TAILLE_MAX_DOC + 1),
                                       content_type="application/pdf")})
    assert DocumentAssurance.objects.count() == 0


@pytest.mark.django_db
def test_la_lecture_ia_ne_rend_rien_sans_ia(client, setup, monkeypatch):
    """Sans Agent IA configuré, on le dit — on n'invente pas de franchise."""
    from ia import llm

    user, _exploitation = setup
    monkeypatch.setattr(llm, "is_configured", lambda: False)
    client.force_login(user)

    resp = client.post("/assurances/scanner/", {
        "document": SimpleUploadedFile("police.pdf", b"%PDF-1.4", content_type="application/pdf")})
    assert resp.status_code == 503
    assert "Agent IA" in resp.json()["error"]

    # Et sans document, on ne part pas en erreur serveur.
    assert client.post("/assurances/scanner/").status_code == 400


@pytest.mark.django_db
def test_la_lecture_ia_prefixe_sans_rien_enregistrer(client, setup, monkeypatch):
    from contrat import assurance_ocr

    user, _exploitation = setup
    monkeypatch.setattr(assurance_ocr, "lire", lambda data, nom: {
        "assureur": "Groupama", "numero_police": "MR-42", "franchise": "500 €",
        "delai_declaration_jours": 5})
    client.force_login(user)

    resp = client.post("/assurances/scanner/", {
        "document": SimpleUploadedFile("police.pdf", b"%PDF-1.4", content_type="application/pdf")})
    assert resp.status_code == 200
    assert resp.json()["champs"]["assureur"] == "Groupama"
    # La lecture ne crée rien : l'exploitant relit puis valide.
    assert Assurance.objects.count() == 0


@pytest.mark.django_db
def test_la_police_du_voisin_est_hors_de_portee(client, setup):
    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin-assur@ex.com", password="pwd12345")
    ferme_voisine = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    sa_police = Assurance.objects.create(exploitation=ferme_voisine, intitule="Sa multirisque")
    son_doc = DocumentAssurance.objects.create(
        assurance=sa_police, fichier="assurances/x.pdf", nom="x.pdf")

    client.force_login(user)
    assert client.post(f"/assurances/{sa_police.pk}/document/", {}).status_code == 404
    assert client.post(f"/assurances/document/{son_doc.pk}/supprimer/").status_code == 404
    assert client.post(f"/assurances/{sa_police.pk}/supprimer/").status_code == 404
