"""Accès aux tiers de l'exploitation (clients, partenaires)."""


def partenaire_de(user, type_partenaire):
    """La fiche partenaire de ce type rattachée au compte, ou None."""
    if user is None or not user.is_authenticated:
        return None
    from .models import Partenaire

    return Partenaire.objects.filter(user=user, type_partenaire=type_partenaire).first()
