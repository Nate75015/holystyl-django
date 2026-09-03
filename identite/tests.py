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
    assert client.post(f"/identite/{piece.pk}/supprimer/").status_code == 404
    assert Piece.objects.filter(pk=piece.pk).exists()


@pytest.mark.django_db
def test_la_section_est_a_part_et_non_dans_finance(client, setup):
    """Les pièces personnelles ne relèvent pas de la comptabilité."""
    user, _exploitation = setup
    client.force_login(user)
    page = client.get("/identite/").content.decode()
    assert 'href="/identite/carte/"' in page
    assert 'href="/identite/passeport/"' in page
    assert 'href="/identite/signature/"' in page
