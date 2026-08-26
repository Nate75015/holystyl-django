"""Récolte rentrée : le fait de production **et** l'entrée en dépôt.

Une récolte est deux choses à la fois, et le projet les tient déjà séparées :
un fait agronomique et économique (`finances.Recolte` — la parcelle, la
qualité, le prix) et une quantité qui arrive physiquement quelque part
(`stock.Mouvement`). Ce module noue les deux, pour qu'aucune ne puisse exister
sans l'autre : une récolte déclarée qui ne gonflerait pas le stock laisserait
le paysan avec un inventaire faux le jour où il veut vendre.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from finances.models import Recolte

from .models import Article, Mouvement, Unite

#: Unités dans lesquelles une récolte peut entrer, et ce que vaut une unité en
#: kilos. Une récolte se pèse : elle n'a pas sa place dans un article tenu en
#: litres, en sacs ou en pièces, où la conversion serait une invention.
KG_PAR_UNITE = {Unite.KG: 1, Unite.TONNE: 1000}


class RecolteRefusee(ValueError):
    """Saisie qu'on ne peut pas enregistrer, avec le motif destiné au paysan."""


def unites_possibles():
    """Les unités qu'un article destinataire peut porter."""
    return [(valeur, label) for valeur, label in Unite.choices if valeur in KG_PAR_UNITE]


def en_unite_article(quantite_kg, article):
    """Convertit des kilos vers l'unité de tenue de l'article."""
    facteur = KG_PAR_UNITE.get(article.unite)
    if facteur is None:
        raise RecolteRefusee(
            _("« %(article)s » est tenu en %(unite)s : une récolte ne peut entrer qu'en kg ou en tonnes.")
            % {"article": article.nom, "unite": article.get_unite_display()}
        )
    return quantite_kg / facteur


@transaction.atomic
def enregistrer(*, exploitation, parcelle, quantite_kg, article=None, nom_article="",
                unite=Unite.KG, depot=None, qualite=Recolte.Qualite.CAT1, prix_unitaire=None,
                cout_main_oeuvre=None, date=None, notes="", user=None):
    """Enregistre une récolte et la fait entrer en stock. Renvoie le couple créé.

    `article` reçoit la récolte ; à défaut, `nom_article` en ouvre un nouveau —
    le paysan qui rentre ses premières tomates ne doit pas avoir à créer une
    fiche article d'abord.
    """
    if parcelle is None:
        raise RecolteRefusee(_("Indiquez la parcelle récoltée."))
    if not quantite_kg or quantite_kg <= 0:
        raise RecolteRefusee(_("Indiquez la quantité récoltée."))

    nom_article = (nom_article or "").strip()
    if article is None and not nom_article:
        raise RecolteRefusee(_("Choisissez l'article qui reçoit la récolte, ou nommez-en un nouveau."))

    prix_unitaire = prix_unitaire or 0
    if article is None:
        if unite not in KG_PAR_UNITE:
            unite = Unite.KG
        article = Article.objects.create(
            exploitation=exploitation,
            nom=nom_article,
            categorie=Article.Categorie.RECOLTE,
            unite=unite,
            depot=depot,
            # Le prix est saisi au kilo ; un article tenu en tonnes se valorise
            # donc à la tonne, sans quoi le stock vaudrait mille fois moins.
            prix_unitaire=(prix_unitaire * KG_PAR_UNITE[unite]) or None,
        )

    quantite = en_unite_article(quantite_kg, article)

    recolte = Recolte.objects.create(
        exploitation=exploitation,
        parcelle=parcelle,
        date=date or timezone.now(),
        quantite_kg=quantite_kg,
        qualite=qualite,
        prix_unitaire=prix_unitaire,
        cout_main_oeuvre=cout_main_oeuvre or 0,
        notes=notes,
    )
    mouvement = Mouvement.objects.create(
        exploitation=exploitation,
        article=article,
        type_mouvement=Mouvement.Type.ENTREE,
        motif=Mouvement.Motif.RECOLTE,
        quantite=quantite,
        recolte=recolte,
        user=user,
        notes=_("Récolte %(parcelle)s") % {"parcelle": parcelle.name},
    )
    return recolte, mouvement
