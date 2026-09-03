"""Les pièces d'identité : ce qui périme, et ce qui ne doit pas fuir."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from exploitations.models import Exploitation
from identite.models import Piece

User = get_user_model()


@pytest.fixture
def setup(db):
    user = User.objects.create_user(email="pieces@ex.com", password="pwd12345")
    return user, Exploitation.objects.create(owner=user, name="Ferme Papiers")


def _fichier(nom="carte.pdf"):
    return SimpleUploadedFile(nom, b"%PDF-1.4 ...", content_type="application/pdf")


@pytest.mark.django_db
def test_les_trois_pieces_ont_leur_onglet(client, setup):
    """Carte, passeport, signature : la section les distingue."""
    user, exploitation = setup
    client.force_login(user)
    for type_piece in ("carte", "passeport", "signature"):
        Piece.objects.create(exploitation=exploitation, type_piece=type_piece,
                             fichier=_fichier(f"{type_piece}.pdf"))

    page = client.get("/identite/").content.decode()
    # L'apostrophe de « Carte d'identité » est échappée dans le rendu.
    for libelle in ("Carte d&#x27;identité", "Passeport", "Signature"):
        assert libelle in page, libelle
    assert "{#" not in page and "{{" not in page

    # Chaque onglet ne montre que son type.
    for type_piece, autre in [("carte", "passeport"), ("signature", "carte")]:
        vues = client.get(f"/identite/{type_piece}/").context["pieces"]
        assert {p.type_piece for p in vues} == {type_piece}, autre


@pytest.mark.django_db
def test_une_piece_qui_perime_remonte_avant_l_echeance(client, setup):
    """On cherche ses papiers dans l'urgence : l'alerte doit précéder."""
    user, exploitation = setup
    aujourdhui = timezone.localdate()
    Piece.objects.create(exploitation=exploitation, type_piece="carte", titulaire="Bientôt",
                         fichier=_fichier(), expire_le=aujourdhui + timedelta(days=40))
    Piece.objects.create(exploitation=exploitation, type_piece="passeport", titulaire="Périmé",
                         fichier=_fichier(), expire_le=aujourdhui - timedelta(days=5))
    Piece.objects.create(exploitation=exploitation, type_piece="carte", titulaire="Tranquille",
                         fichier=_fichier(), expire_le=aujourdhui + timedelta(days=900))
    # Une signature n'expire pas : elle ne doit jamais alerter.
    Piece.objects.create(exploitation=exploitation, type_piece="signature",
                         fichier=_fichier("signature.png"))

    client.force_login(user)
    reponse = client.get("/identite/")
    alertes = {p.titulaire for p in reponse.context["alertes"]}
    assert alertes == {"Bientôt", "Périmé"}
    assert "périmée depuis le" in reponse.content.decode()


@pytest.mark.django_db
def test_le_document_est_filtre_sur_le_format_et_la_taille(client, setup):
    user, _exploitation = setup
    client.force_login(user)

    tableur = SimpleUploadedFile("piece.xlsx", b"PK...", content_type="application/vnd.ms-excel")
    client.post("/identite/ajouter/", {"type_piece": "carte", "fichier": tableur})
    assert Piece.objects.count() == 0

    gros = SimpleUploadedFile("carte.pdf", b"0" * (Piece.TAILLE_MAX + 1),
                              content_type="application/pdf")
    client.post("/identite/ajouter/", {"type_piece": "carte", "fichier": gros})
    assert Piece.objects.count() == 0


@pytest.mark.django_db
def test_ajouter_modifier_supprimer(client, setup):
    user, exploitation = setup
    client.force_login(user)

    assert client.post("/identite/ajouter/", {
        "type_piece": "passeport", "titulaire": "Damien Marque",
        "numero": "17AB12345", "expire_le": "2032-06-30", "fichier": _fichier("pass.pdf"),
    }).status_code == 302

    piece = Piece.objects.get(exploitation=exploitation)
    assert piece.type_piece == "passeport" and piece.numero == "17AB12345"

    client.post(f"/identite/{piece.pk}/modifier/",
                {"type_piece": "passeport", "titulaire": "D. Marque", "numero": "17AB12345"})
    piece.refresh_from_db()
    assert piece.titulaire == "D. Marque"

    assert client.post(f"/identite/{piece.pk}/supprimer/").status_code == 302
    assert Piece.objects.count() == 0


@pytest.mark.django_db
def test_les_pieces_du_voisin_sont_hors_de_portee(client, setup):
    """Des papiers d'identité ne se partagent pas entre exploitations."""
    user, _exploitation = setup
    voisin = User.objects.create_user(email="voisin-pieces@ex.com", password="pwd12345")
    chez_lui = Exploitation.objects.create(owner=voisin, name="Ferme Voisine")
    piece = Piece.objects.create(exploitation=chez_lui, type_piece="carte",
                                 titulaire="Le voisin", fichier=_fichier())

    client.force_login(user)
    assert "Le voisin" not in client.get("/identite/").content.decode()
    # La pièce survit : c'est la propriété qui compte.
    reponse = client.post(f"/identite/{piece.pk}/supprimer/")
    assert reponse.status_code == 302
    assert Piece.objects.filter(pk=piece.pk).exists()

    # Et la réponse est la même que pour une pièce inexistante : distinguer
    # les deux dirait quels identifiants sont pris.
    inexistante = client.post(f"/identite/{piece.pk + 999}/supprimer/")
    assert inexistante.status_code == reponse.status_code
    assert inexistante["Location"] == reponse["Location"]


@pytest.mark.django_db
def test_la_section_est_a_part_et_non_dans_finance(client, setup):
    """Les pièces personnelles ne relèvent pas de la comptabilité."""
    user, _exploitation = setup
    client.force_login(user)
    page = client.get("/identite/").content.decode()
    assert 'href="/identite/carte/"' in page
    assert 'href="/identite/passeport/"' in page
    assert 'href="/identite/signature/"' in page


@pytest.mark.django_db
def test_la_prolongation_deplace_l_echeance_sans_effacer_la_date_imprimee(setup):
    """Deux dates qui ne servent pas au même endroit.

    Les cartes délivrées à un majeur entre 2004 et 2013 valent cinq ans de
    plus en France, sans que la date imprimée change — et plusieurs pays s'en
    tiennent à celle qui est imprimée.
    """
    from datetime import date

    _user, exploitation = setup
    carte = Piece.objects.create(
        exploitation=exploitation, type_piece="carte", fichier=_fichier(),
        expire_le=date(2024, 5, 12), prolongee=True)

    assert carte.expire_le == date(2024, 5, 12)      # ce qui est imprimé
    assert carte.expiration_reelle == date(2029, 5, 12)  # ce qui fait foi
    assert carte.prolongation_douteuse is True
    # L'alerte se règle sur la date réelle : prévenir cinq ans trop tôt
    # serait du bruit.
    assert carte.perimee is False

    sans = Piece.objects.create(exploitation=exploitation, type_piece="carte",
                                fichier=_fichier(), expire_le=date(2024, 5, 12))
    assert sans.expiration_reelle == date(2024, 5, 12)
    assert sans.prolongation_douteuse is False
    assert sans.perimee is True


@pytest.mark.django_db
def test_un_29_fevrier_prolonge_ne_casse_pas(setup):
    """2028 est bissextile, 2033 ne l'est pas."""
    from datetime import date

    _user, exploitation = setup
    carte = Piece.objects.create(exploitation=exploitation, type_piece="carte",
                                 fichier=_fichier(), expire_le=date(2028, 2, 29),
                                 prolongee=True)
    assert carte.expiration_reelle == date(2033, 3, 1)


@pytest.mark.django_db
def test_l_autorite_et_le_nom_d_usage_s_enregistrent(client, setup):
    """La préfecture figure sur la carte : elle se retrouve sur la fiche."""
    user, exploitation = setup
    client.force_login(user)
    client.post("/identite/ajouter/", {
        "type_piece": "carte", "titulaire": "Damien Marque",
        "nom_usage": "Marque-Dupont",
        "autorite": "Préfecture des Alpes-de-Haute-Provence",
        "numero": "D1X4T5R9K", "expire_le": "2031-04-02",
        "fichier": _fichier(),
    })
    piece = Piece.objects.get(exploitation=exploitation)
    assert piece.autorite.startswith("Préfecture")
    assert piece.nom_usage == "Marque-Dupont"

    page = client.get("/identite/carte/").content.decode()
    assert "Préfecture des Alpes-de-Haute-Provence" in page
    assert "Marque-Dupont" in page


@pytest.mark.django_db
def test_la_mise_en_garde_sur_la_prolongation_s_affiche(client, setup):
    user, exploitation = setup
    Piece.objects.create(exploitation=exploitation, type_piece="carte",
                         fichier=_fichier(), expire_le=timezone.localdate(),
                         prolongee=True)
    client.force_login(user)
    page = client.get("/identite/").content.decode()
    assert "refusent cette prolongation" in page


@pytest.mark.django_db
def test_la_lecture_ia_prefixe_sans_rien_enregistrer(client, setup, monkeypatch):
    """Le scan pré-remplit : il ne crée rien tant que la personne n'a pas relu."""
    from identite import ocr

    user, _exploitation = setup
    monkeypatch.setattr(ocr.llm, "is_configured", lambda: True)
    monkeypatch.setattr(ocr.llm, "extract_json_from_document",
                        lambda *a, **k: {"type_piece": "carte",
                                         "titulaire": "Damien Marque",
                                         "numero": "D1X4T5R9K",
                                         "autorite": "Préfecture des Alpes-de-Haute-Provence",
                                         "expire_le": "2031-04-02"})

    client.force_login(user)
    reponse = client.post("/identite/scanner/", {"fichier": _fichier()})
    assert reponse.status_code == 200
    champs = reponse.json()["champs"]
    assert champs["titulaire"] == "Damien Marque"
    assert champs["autorite"].startswith("Préfecture")
    # Les clés absentes de la réponse du modèle sont présentes, à None.
    assert champs["nom_usage"] is None and champs["delivre_le"] is None
    assert Piece.objects.count() == 0


@pytest.mark.django_db
def test_la_lecture_ne_rend_rien_sans_ia(client, setup, monkeypatch):
    from identite import ocr

    user, _exploitation = setup
    monkeypatch.setattr(ocr.llm, "is_configured", lambda: False)
    client.force_login(user)
    assert client.post("/identite/scanner/", {"fichier": _fichier()}).status_code == 503


@pytest.mark.django_db
def test_un_type_hors_referentiel_n_est_pas_retenu(client, setup, monkeypatch):
    """Le modèle ne décide pas seul de la nature de la pièce."""
    from identite import ocr

    user, _exploitation = setup
    monkeypatch.setattr(ocr.llm, "is_configured", lambda: True)
    monkeypatch.setattr(ocr.llm, "extract_json_from_document",
                        lambda *a, **k: {"type_piece": "permis de conduire",
                                         "titulaire": "Damien Marque"})
    client.force_login(user)
    champs = client.post("/identite/scanner/", {"fichier": _fichier()}).json()["champs"]
    assert champs["type_piece"] is None
    assert champs["titulaire"] == "Damien Marque"


def test_la_lecture_ne_demande_que_ce_qui_est_range():
    """Une pièce d'identité en dit bien plus que ce qu'on en garde.

    Chaque champ extrait est une donnée personnelle de plus à protéger : on
    ne demande ni date de naissance, ni adresse, ni taille, ni sexe.
    """
    from identite import ocr

    assert set(ocr.CHAMPS) == {"type_piece", "titulaire", "nom_usage", "numero",
                               "autorite", "delivre_le", "expire_le"}
    for interdit in ("date_naissance", "lieu_naissance", "adresse", "taille", "sexe"):
        assert interdit not in ocr.CHAMPS
    # Le prompt le dit au modèle, pas seulement le filtre de sortie.
    assert "ignore la date et le lieu" in ocr._PROMPT


@pytest.mark.django_db
def test_la_signature_se_trace_a_l_ecran_et_devient_active(client, setup):
    """Un trait au doigt vaut signature : on le range en image, pas en base64."""
    import base64

    from PIL import Image

    user, exploitation = setup
    client.force_login(user)

    import io

    buf = io.BytesIO()
    Image.new("RGBA", (240, 80), (0, 0, 0, 0)).save(buf, "PNG")
    trace = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    assert client.post("/identite/signature/definir/",
                       {"trace": trace, "titulaire": "Damien Marque"}).status_code == 302

    piece = Piece.objects.get(exploitation=exploitation)
    assert piece.type_piece == "signature" and piece.par_defaut is True
    assert piece.fichier.name.endswith(".png")
    assert Piece.signature_active(exploitation) == piece


@pytest.mark.django_db
def test_un_trace_illisible_est_refuse(client, setup):
    user, _exploitation = setup
    client.force_login(user)
    for mauvais in ("", "pas une data url", "data:image/png;base64,@@@"):
        client.post("/identite/signature/definir/", {"trace": mauvais})
    assert Piece.objects.count() == 0


@pytest.mark.django_db
def test_une_seule_signature_active_a_la_fois(client, setup):
    user, exploitation = setup
    ancienne = Piece.objects.create(exploitation=exploitation, type_piece="signature",
                                    fichier=_fichier("une.png"), par_defaut=True)
    nouvelle = Piece.objects.create(exploitation=exploitation, type_piece="signature",
                                    fichier=_fichier("deux.png"))

    client.force_login(user)
    client.post(f"/identite/signature/{nouvelle.pk}/activer/")
    ancienne.refresh_from_db(); nouvelle.refresh_from_db()
    assert nouvelle.par_defaut is True and ancienne.par_defaut is False
    assert Piece.signature_active(exploitation) == nouvelle


@pytest.mark.django_db
def test_sans_signature_designee_la_plus_recente_sert(setup):
    """Mieux vaut une signature que rien sur un contrat qui part au salarié."""
    _user, exploitation = setup
    Piece.objects.create(exploitation=exploitation, type_piece="signature",
                         fichier=_fichier("vieille.png"))
    recente = Piece.objects.create(exploitation=exploitation, type_piece="signature",
                                   fichier=_fichier("recente.png"))
    assert Piece.signature_active(exploitation) == recente
    # Une carte d'identité n'est jamais prise pour une signature.
    Piece.objects.create(exploitation=exploitation, type_piece="carte", fichier=_fichier())
    assert Piece.signature_active(exploitation).est_signature is True


@pytest.mark.django_db
def test_le_pave_n_apparait_que_sur_l_onglet_signature(client, setup):
    user, _exploitation = setup
    client.force_login(user)
    assert 'x-ref="toile"' in client.get("/identite/signature/").content.decode()
    for autre in ("/identite/", "/identite/carte/", "/identite/passeport/"):
        assert 'x-ref="toile"' not in client.get(autre).content.decode(), autre


@pytest.mark.django_db
def test_une_page_perimee_ne_montre_pas_un_ecran_d_erreur(client, setup):
    """Deux onglets, un retour arrière : la pièce a pu disparaître entre-temps.

    C'est une situation ordinaire, pas une anomalie — elle mérite un message
    et un retour à la liste, pas une page 404 de débogage.
    """
    user, exploitation = setup
    piece = Piece.objects.create(exploitation=exploitation, type_piece="carte",
                                 fichier=_fichier())
    client.force_login(user)
    piece_pk = piece.pk
    piece.delete()

    for url in (f"/identite/{piece_pk}/supprimer/", f"/identite/{piece_pk}/modifier/",
                f"/identite/signature/{piece_pk}/activer/"):
        reponse = client.post(url, follow=True)
        assert reponse.status_code == 200, url
        assert "n&#x27;existe plus" in reponse.content.decode(), url


def _toile(taille=(400, 100), trace=None):
    """Une toile transparente, avec au besoin un trait noir posé dessus."""
    import io

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", taille, (0, 0, 0, 0))
    if trace:
        ImageDraw.Draw(image).rectangle(trace, fill=(0, 0, 0, 255))
    sortie = io.BytesIO()
    image.save(sortie, format="PNG")
    return sortie.getvalue()


def _taille(binaire):
    import io

    from PIL import Image

    return Image.open(io.BytesIO(binaire)).size


def test_la_signature_est_rognee_sur_son_trace():
    """Le pavé est une bande large : sans rognage, le trait s'imprime en filet."""
    from identite.signatures import recadrer

    # Un trait de 100 × 40 au milieu d'une toile de 400 × 100.
    largeur, hauteur = _taille(recadrer(_toile(trace=(150, 30, 250, 70))))
    assert 100 < largeur < 130 and 40 < hauteur < 70  # le trait, plus une marge
    # Le rapport passe de 4:1 à environ 2:1 — c'est ce qui la rend lisible.
    assert largeur / hauteur < 2.5


def test_une_toile_vide_reste_intacte():
    """Rien à rogner : mieux vaut le fichier d'origine qu'une image nulle."""
    from identite.signatures import recadrer

    vide = _toile()
    assert recadrer(vide) == vide


def test_un_fichier_illisible_traverse_sans_dommage():
    """Une signature abîmée vaudrait moins qu'une signature petite."""
    from identite.signatures import recadrer

    assert recadrer(b"%PDF-1.4 pas une image") == b"%PDF-1.4 pas une image"


def test_une_signature_photographiee_perd_ses_marges_blanches():
    """Sans transparence, c'est le blanc qui fait la marge."""
    import io

    from PIL import Image, ImageDraw

    from identite.signatures import recadrer

    image = Image.new("RGB", (400, 100), "white")
    ImageDraw.Draw(image).rectangle((150, 30, 250, 70), fill="black")
    sortie = io.BytesIO()
    image.save(sortie, format="PNG")

    largeur, _hauteur = _taille(recadrer(sortie.getvalue()))
    assert largeur < 140
