"""Accès aux contrats et baux."""


def baux_du_bailleur(partenaire, limite=None):
    """Les baux consentis par ce bailleur, du plus récent au plus ancien.

    Le rattachement passe par la FK `Bail.partenaire`, pas par le champ texte
    `Bail.bailleur` : comparer des noms saisis à la main donnerait à un bailleur
    la vue des baux d'un homonyme.
    """
    if partenaire is None:
        return []
    from .models import Bail

    baux = Bail.objects.filter(partenaire=partenaire).select_related("exploitation")
    return list(baux[:limite] if limite else baux)


def totaux_baux(baux):
    """(surface louée en ha, fermage annuel en €) pour une liste de baux.

    Renvoie None plutôt que 0 quand rien n'est renseigné : le template affiche
    « — », ce qui distingue « pas de donnée » de « zéro hectare ».
    """
    surface = round(sum(b.surface_ha or 0 for b in baux), 2)
    loyer = round(sum(b.loyer_annuel or 0 for b in baux), 2)
    return (surface or None), (loyer or None)
