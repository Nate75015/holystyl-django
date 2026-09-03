"""Tests contrat : assurances, baux et actes notariés.

Même trame pour les trois : statut, échéance qui ne se rattrape pas,
documents joints, lecture IA sans écriture, et cloisonnement par ferme.
"""

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


# ── Baux : délais de congé, documents, lecture IA ────────────────────


def _bail(**surcharges):
    champs = {
        "designation": "Parcelles des Coteaux",
        "type_bail": "ferme_9",
        "statut": "actif",
        "bailleur": "SCI des Coteaux",
        "preneur": "EARL du Ventoux",
        "contact_telephone": "0490112233",
        "surface_ha": "12,40",
        "loyer_annuel": "1 860",
        "date_debut": "2024-11-11",
        "date_fin": "2033-11-11",
        "preavis_conge_mois": "18",
        "renouvellement_tacite": "on",
        "taxe_fonciere_part_preneur": "20",
        "references_cadastrales": "ZA 12, ZA 14",
        "etat_des_lieux": "on",
    }
    champs.update(surcharges)
    return champs


@pytest.mark.django_db
def test_enregistrer_un_bail_avec_ses_delais(client, setup):
    from contrat.models import Bail

    user, exploitation = setup
    client.force_login(user)
    assert client.post("/baux/nouveau/", _bail()).status_code == 302

    b = Bail.objects.get(exploitation=exploitation)
    assert b.type_bail == "ferme_9" and b.surface_ha == 12.4
    assert b.preavis_conge_mois == 18 and b.renouvellement_tacite is True
    assert b.taxe_fonciere_part_preneur == 20 and b.etat_des_lieux is True
    assert b.references_cadastrales == "ZA 12, ZA 14"


@pytest.mark.django_db
def test_la_date_limite_de_conge_recule_du_preavis(setup):
    """Dix-huit mois avant le terme : passée, le bail se renouvelle."""
    from datetime import date

    from contrat.models import Bail

    _user, exploitation = setup
    b = Bail.objects.create(exploitation=exploitation, designation="Coteaux",
                            date_fin=date(2033, 11, 11), preavis_conge_mois=18)
    assert b.date_limite_conge == date(2032, 5, 11)

    # Fin de mois et année bissextile : le jour est borné, pas débordé.
    b.date_fin = date(2033, 8, 31)
    assert b.date_limite_conge == date(2032, 2, 29)

    # Sans terme, il n'y a pas de fenêtre de congé.
    b.date_fin = None
    assert b.date_limite_conge is None and b.jours_avant_conge is None


@pytest.mark.django_db
def test_le_conge_imminent_remonte_sur_la_page(client, setup):
    from datetime import timedelta

    from contrat.models import Bail

    user, exploitation = setup
    # Terme dans 18 mois et 3 mois : la fenêtre de congé se ferme dans 3 mois.
    Bail.objects.create(
        exploitation=exploitation, designation="Coteaux", statut="actif",
        preavis_conge_mois=18,
        date_fin=timezone.localdate() + timedelta(days=548 + 90))
    # Terme lointain : rien à signaler.
    Bail.objects.create(
        exploitation=exploitation, designation="Plaine", statut="actif",
        preavis_conge_mois=18,
        date_fin=timezone.localdate() + timedelta(days=548 + 900))

    client.force_login(user)
    resp = client.get("/baux/")
    assert [b.designation for b in resp.context["conges_imminents"]] == ["Coteaux"]
    html = resp.content.decode()
    assert "congé est à donner bientôt" in html
    assert "se renouvelle de plein droit" in html
    assert "{#" not in html and "{{" not in html


@pytest.mark.django_db
def test_joindre_un_bail_scanne(client, setup):
    from contrat.models import Bail, DocumentBail

    user, exploitation = setup
    b = Bail.objects.create(exploitation=exploitation, designation="Coteaux")
    client.force_login(user)

    assert client.post(f"/baux/{b.pk}/document/", {
        "document": SimpleUploadedFile("bail.pdf", b"%PDF-1.4", content_type="application/pdf"),
        "type_document": "bail"}).status_code == 302
    assert DocumentBail.objects.get(bail=b).type_document == "bail"

    # Un exécutable est refusé, comme pour les assurances.
    client.post(f"/baux/{b.pk}/document/", {
        "document": SimpleUploadedFile("bail.exe", b"MZ", content_type="application/octet-stream")})
    assert DocumentBail.objects.count() == 1


@pytest.mark.django_db
def test_la_lecture_ia_du_bail_prefixe_sans_enregistrer(client, setup, monkeypatch):
    from contrat import bail_ocr
    from contrat.models import Bail

    user, _exploitation = setup
    monkeypatch.setattr(bail_ocr, "lire", lambda data, nom: {
        "designation": "Parcelles des Coteaux", "surface_ha": 12.4,
        "preavis_conge_mois": 18, "type_bail": "ferme_9"})
    client.force_login(user)

    resp = client.post("/baux/scanner/", {
        "document": SimpleUploadedFile("bail.pdf", b"%PDF-1.4", content_type="application/pdf")})
    assert resp.status_code == 200
    assert resp.json()["champs"]["surface_ha"] == 12.4
    assert Bail.objects.count() == 0


@pytest.mark.django_db
def test_le_bail_du_voisin_est_hors_de_portee(client, setup):
    from contrat.models import Bail, DocumentBail

    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin-bail@ex.com", password="pwd12345")
    ferme_voisine = Exploitation.objects.create(owner=voisin, name="Ferme voisine")
    son_bail = Bail.objects.create(exploitation=ferme_voisine, designation="Ses terres")
    son_doc = DocumentBail.objects.create(bail=son_bail, fichier="baux/x.pdf", nom="x.pdf")

    client.force_login(user)
    assert client.post(f"/baux/{son_bail.pk}/document/", {}).status_code == 404
    assert client.post(f"/baux/document/{son_doc.pk}/supprimer/").status_code == 404
    assert client.post(f"/baux/{son_bail.pk}/supprimer/").status_code == 404


# ── Actes notariés ──────────────────────────────────────────────────
#
# Un acte notarié se manque sur deux dates : la réitération d'un compromis et
# la péremption d'une inscription hypothécaire. Le reste est de l'archivage.


def _acte(**surcharges):
    champs = {
        "objet": "Achat parcelle ZA 42",
        "type_acte": "achat",
        "statut": "signe",
        "notaire": "Étude Berger & Associés",
        "telephone_notaire": "0490445566",
        "email_notaire": "etude@berger.example",
        "parties": "Consorts Roux / EARL du Ventoux",
        "reference": "2025/1187",
        "date_signature": "2025-06-18",
        "surface_ha": "8,60",
        "references_cadastrales": "ZA 42, ZA 43",
        "montant": "94 000",
        "frais_notaire": "7 300",
        "droits_enregistrement": "5 100",
        "conditions_suspensives": "Obtention du prêt, purge SAFER",
        "charges_et_servitudes": "Servitude de passage au nord",
        "droit_preemption": "SAFER — deux mois",
    }
    champs.update(surcharges)
    return champs


@pytest.mark.django_db
def test_enregistrer_un_acte_avec_ses_conditions(client, setup):
    from contrat.models import ActeNotarie

    user, exploitation = setup
    client.force_login(user)
    assert client.post("/actes-notaries/nouveau/", _acte()).status_code == 302

    a = ActeNotarie.objects.get(exploitation=exploitation)
    assert a.type_acte == "achat" and a.statut == "signe"
    assert a.surface_ha == 8.6 and a.montant == 94000
    assert a.frais_et_droits == 12400 and a.cout_total == 106400
    assert a.droit_preemption.startswith("SAFER")
    assert a.est_en_vigueur is True


@pytest.mark.django_db
def test_un_acte_sans_objet_n_est_pas_cree(client, setup):
    from contrat.models import ActeNotarie

    user, _exploitation = setup
    client.force_login(user)
    client.post("/actes-notaries/nouveau/", _acte(objet="   "))
    assert ActeNotarie.objects.count() == 0


@pytest.mark.django_db
def test_la_promesse_expire_et_l_hypotheque_se_perime(setup):
    """Les deux échéances qui ne se rattrapent pas, et rien d'autre."""
    from datetime import date

    from contrat.models import ActeNotarie

    _user, exploitation = setup

    promesse = ActeNotarie.objects.create(
        exploitation=exploitation, objet="Compromis Plaine", type_acte="achat",
        statut="promesse", date_limite_realisation=date(2030, 4, 15))
    assert promesse.date_limite_action == date(2030, 4, 15)
    assert "Réitérer" in str(promesse.action_a_mener)

    hypo = ActeNotarie.objects.create(
        exploitation=exploitation, objet="Prêt bâtiment", type_acte="hypotheque",
        statut="signe", date_peremption=date(2031, 9, 1))
    assert hypo.date_limite_action == date(2031, 9, 1)
    assert "mainlevée" in str(hypo.action_a_mener)

    # Mainlevée obtenue : l'inscription ne pèse plus, il n'y a plus rien à faire.
    hypo.mainlevee_obtenue = True
    assert hypo.date_limite_action is None and hypo.action_a_mener is None

    # Une vente signée n'a aucune échéance de ce genre.
    vente = ActeNotarie.objects.create(
        exploitation=exploitation, objet="Vente pré", type_acte="vente",
        statut="publie", date_signature=date(2024, 3, 2))
    assert vente.date_limite_action is None and vente.jours_avant_action is None


@pytest.mark.django_db
def test_l_action_imminente_remonte_sur_la_page(client, setup):
    from contrat.models import ActeNotarie

    user, exploitation = setup
    ActeNotarie.objects.create(
        exploitation=exploitation, objet="Compromis Plaine", type_acte="achat",
        statut="promesse",
        date_limite_realisation=timezone.localdate() + timedelta(days=30))
    ActeNotarie.objects.create(
        exploitation=exploitation, objet="Compromis lointain", type_acte="achat",
        statut="promesse",
        date_limite_realisation=timezone.localdate() + timedelta(days=400))

    client.force_login(user)
    resp = client.get("/actes-notaries/")
    assert [a.objet for a in resp.context["actions_imminentes"]] == ["Compromis Plaine"]
    html = resp.content.decode()
    assert "demande une action" in html
    assert "{#" not in html and "{{" not in html


@pytest.mark.django_db
def test_le_delai_depasse_reste_visible(client, setup):
    """Une échéance manquée ne disparaît pas : c'est là qu'elle compte."""
    from contrat.models import ActeNotarie

    user, exploitation = setup
    acte = ActeNotarie.objects.create(
        exploitation=exploitation, objet="Compromis échu", type_acte="achat",
        statut="promesse",
        date_limite_realisation=timezone.localdate() - timedelta(days=10))
    assert acte.action_depassee is True and acte.action_imminente is False

    client.force_login(user)
    resp = client.get("/actes-notaries/")
    assert [a.objet for a in resp.context["actions_imminentes"]] == ["Compromis échu"]
    assert "délai dépassé" in resp.content.decode()


@pytest.mark.django_db
def test_signe_mais_non_publie_est_signale(client, setup):
    """Entre les parties, oui ; contre les tiers, pas encore."""
    from contrat.models import ActeNotarie

    user, exploitation = setup
    ActeNotarie.objects.create(exploitation=exploitation, objet="Achat ZA 42",
                               type_acte="achat", statut="signe")
    # Une procuration ne se publie pas : elle ne doit rien déclencher.
    ActeNotarie.objects.create(exploitation=exploitation, objet="Procuration",
                               type_acte="procuration", statut="signe")

    client.force_login(user)
    resp = client.get("/actes-notaries/")
    assert [a.objet for a in resp.context["publications_attendues"]] == ["Achat ZA 42"]
    assert "inopposable aux tiers" in resp.content.decode()


@pytest.mark.django_db
def test_joindre_un_acte_scanne(client, setup):
    from contrat.models import ActeNotarie, DocumentActe

    user, exploitation = setup
    client.force_login(user)
    client.post("/actes-notaries/nouveau/", _acte())
    acte = ActeNotarie.objects.get(exploitation=exploitation)

    fichier = SimpleUploadedFile("acte.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    resp = client.post(f"/actes-notaries/{acte.pk}/document/",
                       {"document": fichier, "type_document": "titre"})
    assert resp.status_code == 302
    doc = DocumentActe.objects.get(acte=acte)
    assert doc.type_document == "titre" and doc.nom == "acte.pdf"

    assert client.post(f"/actes-notaries/document/{doc.pk}/supprimer/").status_code == 302
    assert DocumentActe.objects.count() == 0


@pytest.mark.django_db
def test_le_document_d_acte_est_filtre_sur_le_format(client, setup):
    from contrat.models import ActeNotarie, DocumentActe

    user, exploitation = setup
    acte = ActeNotarie.objects.create(exploitation=exploitation, objet="Achat")
    client.force_login(user)

    tableur = SimpleUploadedFile("acte.xlsx", b"PK...", content_type="application/vnd.ms-excel")
    client.post(f"/actes-notaries/{acte.pk}/document/", {"document": tableur})
    assert DocumentActe.objects.count() == 0


@pytest.mark.django_db
def test_la_lecture_ia_de_l_acte_prefixe_sans_enregistrer(client, setup, monkeypatch):
    """Le scan pré-remplit : il ne crée rien tant que l'exploitant n'a pas relu."""
    from contrat import acte_ocr
    from contrat.models import ActeNotarie

    user, _exploitation = setup
    monkeypatch.setattr(acte_ocr.llm, "is_configured", lambda: True)
    monkeypatch.setattr(acte_ocr.llm, "extract_json_from_document",
                        lambda *a, **k: {"objet": "Achat ZA 42", "type_acte": "achat",
                                         "montant": 94000, "surface_ha": 8.6})

    client.force_login(user)
    fichier = SimpleUploadedFile("acte.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    resp = client.post("/actes-notaries/scanner/", {"document": fichier})
    assert resp.status_code == 200
    champs = resp.json()["champs"]
    assert champs["objet"] == "Achat ZA 42" and champs["montant"] == 94000
    # Les clés absentes de la réponse du modèle sont présentes, à None.
    assert champs["date_limite_realisation"] is None
    assert ActeNotarie.objects.count() == 0


@pytest.mark.django_db
def test_la_lecture_ia_de_l_acte_ne_rend_rien_sans_ia(client, setup, monkeypatch):
    from contrat import acte_ocr

    user, _exploitation = setup
    monkeypatch.setattr(acte_ocr.llm, "is_configured", lambda: False)

    client.force_login(user)
    fichier = SimpleUploadedFile("acte.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    resp = client.post("/actes-notaries/scanner/", {"document": fichier})
    assert resp.status_code == 503


@pytest.mark.django_db
def test_l_acte_du_voisin_est_hors_de_portee(client, setup):
    from contrat.models import ActeNotarie

    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin-acte@ex.com", password="pwd12345")
    chez_lui = Exploitation.objects.create(owner=voisin, name="Ferme Voisine")
    acte = ActeNotarie.objects.create(exploitation=chez_lui, objet="Achat du voisin")

    client.force_login(user)
    assert client.post(f"/actes-notaries/{acte.pk}/supprimer/").status_code == 404
    assert ActeNotarie.objects.filter(pk=acte.pk).exists()
