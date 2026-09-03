"""Rogne les signatures déjà enregistrées sur leur tracé.

Le pavé de saisie produit une bande large où l'on signe au milieu : les
signatures d'avant occupent un dixième de leur fichier, et s'impriment donc
en filet au bas des contrats. On les recadre une fois pour toutes.

Seuls des pixels vides disparaissent, et un fichier qui résiste est laissé
tel quel : une signature abîmée vaut moins qu'une signature petite.
"""

from django.core.files.base import ContentFile
from django.db import migrations


def recadrer_les_signatures(apps, schema_editor):
    from identite.signatures import recadrer

    Piece = apps.get_model("identite", "Piece")
    for piece in Piece.objects.filter(type_piece="signature").exclude(fichier=""):
        try:
            with piece.fichier.open("rb") as ouvert:
                avant = ouvert.read()
        except Exception:  # noqa: BLE001 — fichier absent ou stockage distant
            continue
        apres = recadrer(avant)
        if apres == avant:
            continue
        piece.fichier.save(piece.fichier.name.rsplit("/", 1)[-1], ContentFile(apres), save=True)


class Migration(migrations.Migration):

    dependencies = [("identite", "0003_piece_par_defaut")]

    operations = [migrations.RunPython(recadrer_les_signatures, migrations.RunPython.noop)]
