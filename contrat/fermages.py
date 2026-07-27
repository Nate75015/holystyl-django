"""Révision du fermage par l'indice national.

Le loyer d'un bail rural est fixé en € par hectare pour une année de référence,
puis révisé chaque année en appliquant la variation de l'indice national des
fermages. Le résultat doit rester dans la fourchette de l'arrêté préfectoral.
"""

from decimal import Decimal


def indices_appliques(indices, annee_reference, annee_cible):
    """Indices à appliquer pour passer de l'année de référence à l'année cible.

    `indices` : dict {année: variation en %}. On applique les indices des années
    postérieures à la référence, jusqu'à l'année cible incluse.
    """
    if annee_reference is None or annee_cible is None:
        return []
    return [
        {"annee": annee, "variation_pct": indices[annee]}
        for annee in sorted(indices)
        if annee_reference < annee <= annee_cible
    ]


def reviser(loyer_base_ha, indices, annee_reference, annee_cible):
    """Loyer révisé en €/ha, et détail des indices appliqués.

    Renvoie (loyer_revise, appliques). Sans loyer de base ou sans indice
    applicable, le loyer de base est renvoyé tel quel : jamais d'invention.
    """
    appliques = indices_appliques(indices, annee_reference, annee_cible)
    if loyer_base_ha is None:
        return None, appliques
    loyer = Decimal(str(loyer_base_ha))
    for indice in appliques:
        loyer *= Decimal(1) + Decimal(str(indice["variation_pct"])) / Decimal(100)
    return float(round(loyer, 2)), appliques


def conformite(loyer_ha, mini_ha, maxi_ha):
    """Position du loyer vis-à-vis de l'encadrement préfectoral.

    Renvoie « conforme », « sous_mini », « au_dessus_maxi », ou « inconnue »
    quand l'encadrement n'est pas renseigné (aucun jugement dans ce cas).
    """
    if loyer_ha is None or (mini_ha is None and maxi_ha is None):
        return "inconnue"
    if mini_ha is not None and loyer_ha < mini_ha:
        return "sous_mini"
    if maxi_ha is not None and loyer_ha > maxi_ha:
        return "au_dessus_maxi"
    return "conforme"


def ligne_bail(bail, indices, annee_cible):
    """Ligne de calcul prête à afficher pour un bail."""
    base_ha = bail.loyer_base_ha
    # À défaut de loyer de base saisi, on le déduit du fermage annuel connu.
    deduit = False
    if base_ha is None and bail.loyer_annuel and bail.surface_ha:
        base_ha = round(bail.loyer_annuel / bail.surface_ha, 2)
        deduit = True
    revise_ha, appliques = reviser(base_ha, indices, bail.annee_reference, annee_cible)
    total = round(revise_ha * bail.surface_ha, 2) if revise_ha and bail.surface_ha else None
    return {
        "bail": bail,
        "base_ha": base_ha,
        "base_deduite": deduit,
        "indices": appliques,
        "revise_ha": revise_ha,
        "total_annuel": total,
        "conformite": conformite(revise_ha, bail.loyer_mini_ha, bail.loyer_maxi_ha),
    }
