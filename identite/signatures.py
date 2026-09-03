"""Recadrage d'une signature sur son tracé.

Le pavé de saisie est une bande large, et l'on signe rarement d'un bord à
l'autre : le fichier obtenu est surtout du vide. Posé dans un contrat, il
s'affiche alors en filet, puisque c'est la toile qui remplit la place et non
le trait. On rogne donc les marges vides avant d'enregistrer.

Rien n'est perdu : seuls des pixels transparents — ou blancs, pour une photo
de signature — disparaissent. En cas de doute (format illisible, image vide,
Pillow absent), on rend le fichier d'origine plutôt que d'abîmer une pièce
qui s'appose sur des documents signés.
"""

from __future__ import annotations

import io

#: Une marge autour du trait, pour qu'il ne touche pas le bord.
_MARGE = 0.06
#: Au-delà, on considère le pixel comme du fond blanc.
_SEUIL_BLANC = 246


def recadrer(binaire: bytes) -> bytes:
    """La signature réduite à son tracé, ou le fichier d'origine."""
    try:
        from PIL import Image
    except ImportError:  # Pillow absent : on n'invente rien
        return binaire
    try:
        image = Image.open(io.BytesIO(binaire))
        image.load()
    except Exception:  # noqa: BLE001 — format illisible : on garde l'original
        return binaire

    image = image.convert("RGBA")
    boite = _boite_du_trace(image)
    if boite is None:
        return binaire  # toile vide : rien à recadrer

    gauche, haut, droite, bas = boite
    marge = max(6, round(_MARGE * max(droite - gauche, bas - haut)))
    recadree = image.crop((
        max(0, gauche - marge), max(0, haut - marge),
        min(image.width, droite + marge), min(image.height, bas + marge)))

    sortie = io.BytesIO()
    recadree.save(sortie, format="PNG", optimize=True)
    return sortie.getvalue()


def _boite_du_trace(image):
    """Ce qui entoure l'encre : par la transparence, sinon par le blanc."""
    from PIL import Image, ImageChops

    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:  # l'image porte de la transparence
        return alpha.getbbox()
    # Signature photographiée ou aplatie sur blanc : on cherche ce qui tranche.
    gris = image.convert("L").point(lambda ton: 255 if ton >= _SEUIL_BLANC else 0)
    return ImageChops.difference(gris, Image.new("L", gris.size, 255)).getbbox()
