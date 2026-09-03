"""Qui peut faire quoi sur le planning d'une exploitation.

Le partage se lit comme celui d'un agenda en ligne : le chef d'exploitation
possède le sien, tous les autres demandent l'accès et l'obtiennent à un niveau
— lecture, écriture, ou gestion des accès. Un niveau contient les précédents :
qui peut gérer peut écrire, qui peut écrire peut lire.

Ce module est la seule autorité sur la question. Les vues s'y adressent plutôt
que de recalculer chacune sa règle.
"""

from django.utils import timezone

from .models import AccesPlanning

#: Force relative des niveaux. Comparer des rangs plutôt que des chaînes évite
#: d'écrire « lecture ou écriture ou gestion » à chaque contrôle.
RANG = {
    AccesPlanning.Niveau.LECTURE: 1,
    AccesPlanning.Niveau.ECRITURE: 2,
    AccesPlanning.Niveau.GESTION: 3,
}


def est_proprietaire(exploitation, user):
    """Le chef d'exploitation : son planning, tous les droits, sans ligne en base."""
    return bool(exploitation) and user.is_authenticated and exploitation.owner_id == user.id


def niveau_de(exploitation, user):
    """Le niveau du compte sur ce planning, ou None s'il n'y a pas accès."""
    if not exploitation or not getattr(user, "is_authenticated", False):
        return None
    if est_proprietaire(exploitation, user):
        return AccesPlanning.Niveau.GESTION
    acces = AccesPlanning.objects.filter(
        exploitation=exploitation, user=user, statut=AccesPlanning.Statut.ACCORDE).first()
    return acces.niveau if acces else None


def _au_moins(exploitation, user, niveau_requis):
    niveau = niveau_de(exploitation, user)
    return niveau is not None and RANG[niveau] >= RANG[niveau_requis]


def peut_lire(exploitation, user):
    return _au_moins(exploitation, user, AccesPlanning.Niveau.LECTURE)


def peut_ecrire(exploitation, user):
    return _au_moins(exploitation, user, AccesPlanning.Niveau.ECRITURE)


def peut_gerer(exploitation, user):
    return _au_moins(exploitation, user, AccesPlanning.Niveau.GESTION)


def demande_en_cours(exploitation, user):
    """La demande du compte, quel que soit son sort — pour savoir quoi lui dire."""
    if not exploitation or not getattr(user, "is_authenticated", False):
        return None
    return AccesPlanning.objects.filter(exploitation=exploitation, user=user).first()


def demander(exploitation, user, message=""):
    """Dépose ou relance une demande d'accès.

    Une demande refusée peut être reposée : on remet le compteur à zéro plutôt
    que de laisser un refus fermer la porte définitivement.
    """
    acces, _cree = AccesPlanning.objects.get_or_create(
        exploitation=exploitation, user=user,
        defaults={"message": message[:2000]})
    if acces.statut != AccesPlanning.Statut.ACCORDE:
        acces.statut = AccesPlanning.Statut.EN_ATTENTE
        acces.message = message[:2000] or acces.message
        acces.decide_par = None
        acces.decide_le = None
        acces.save(update_fields=["statut", "message", "decide_par", "decide_le", "updated_at"])
    return acces


def decider(acces, *, statut, niveau, par):
    """Accorde ou refuse une demande, en gardant qui a tranché et quand."""
    acces.statut = statut
    if niveau in RANG:
        acces.niveau = niveau
    acces.decide_par = par
    acces.decide_le = timezone.now()
    acces.save(update_fields=["statut", "niveau", "decide_par", "decide_le", "updated_at"])
    return acces


def gestionnaires(exploitation):
    """Les comptes à prévenir d'une demande : le chef, et qui gère les accès."""
    comptes = {exploitation.owner} if exploitation.owner_id else set()
    for acces in (AccesPlanning.objects
                  .filter(exploitation=exploitation,
                          statut=AccesPlanning.Statut.ACCORDE,
                          niveau=AccesPlanning.Niveau.GESTION)
                  .select_related("user")):
        comptes.add(acces.user)
    return comptes
