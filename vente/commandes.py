"""Cycle de vie d'une commande : de la validation du panier au retrait.

Deux règles tiennent tout le reste :

* une commande ne concerne qu'une ferme — un panier multi-fermes se scinde ;
* le stock ne **sort** qu'au moment où la marchandise part réellement. Avant,
  elle est seulement promise (cf. `Commande.RESERVANTS`), et cette promesse se
  déduit de la disponibilité affichée. Le dépôt ne ment jamais sur ce qu'il
  contient.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from notifications.services import notify
from stock.models import Mouvement

from . import facturation
from . import panier as panier_service
from .models import Commande, LigneCommande, Produit

#: Transitions permises : depuis quels statuts, vers lequel. Écrire la table
#: plutôt que des `if` disséminés, c'est pouvoir répondre « non » à une action
#: qui arrive deux fois (double clic, retour arrière du navigateur).
TRANSITIONS = {
    "confirmer": ((Commande.Statut.NOUVELLE,), Commande.Statut.CONFIRMEE),
    "refuser": ((Commande.Statut.NOUVELLE,), Commande.Statut.REFUSEE),
    "prete": ((Commande.Statut.CONFIRMEE,), Commande.Statut.PRETE),
    "servir": ((Commande.Statut.CONFIRMEE, Commande.Statut.PRETE), Commande.Statut.SERVIE),
    "annuler": ((Commande.Statut.NOUVELLE, Commande.Statut.CONFIRMEE, Commande.Statut.PRETE),
                Commande.Statut.ANNULEE),
}

HORODATAGE = {
    Commande.Statut.CONFIRMEE: "confirmee_le",
    Commande.Statut.PRETE: "prete_le",
    Commande.Statut.SERVIE: "servie_le",
}


class CommandeRefusee(ValueError):
    """Commande qu'on ne peut pas enregistrer, avec le motif pour l'acheteur."""


def _verifier_disponible(produit, quantite):
    if quantite < (produit.quantite_min or 0):
        raise CommandeRefusee(
            _("« %(produit)s » se commande par %(min)s minimum.")
            % {"produit": produit.nom, "min": produit.quantite_min}
        )
    disponible = produit.disponible
    if disponible is not None and quantite > disponible:
        raise CommandeRefusee(
            _("Il ne reste que %(reste)s de « %(produit)s ».")
            % {"reste": disponible, "produit": produit.nom}
        )


@transaction.atomic
def creer_depuis_panier(request, *, nom, email="", telephone="", mode_retrait=Commande.Retrait.FERME,
                        adresse_livraison="", date_souhaitee=None, creneau="", notes=""):
    """Valide le panier et crée une commande par ferme. Renvoie les commandes.

    La disponibilité est revérifiée ici : entre la mise au panier et la
    validation, un autre acheteur a pu passer devant.
    """
    groupes = panier_service.groupes(request)
    if not groupes:
        raise CommandeRefusee(_("Votre panier est vide."))
    if not (nom or "").strip():
        raise CommandeRefusee(_("Indiquez votre nom."))
    if not (email or "").strip() and not (telephone or "").strip():
        raise CommandeRefusee(_("Laissez un email ou un téléphone : la ferme doit pouvoir vous répondre."))

    utilisateur = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    commandes = []

    for groupe in groupes:
        exploitation = groupe["exploitation"]
        for ligne in groupe["lignes"]:
            _verifier_disponible(ligne["produit"], ligne["quantite"])

        commande = Commande.objects.create(
            exploitation=exploitation,
            client_ref=_fiche_client(utilisateur, exploitation),
            acheteur_nom=nom.strip(),
            acheteur_email=(email or "").strip(),
            acheteur_telephone=(telephone or "").strip(),
            mode_retrait=mode_retrait,
            adresse_livraison=(adresse_livraison or "").strip(),
            date_souhaitee=date_souhaitee,
            creneau=(creneau or "").strip(),
            notes=(notes or "").strip(),
        )
        for ligne in groupe["lignes"]:
            produit = ligne["produit"]
            LigneCommande.objects.create(
                commande=commande,
                produit=produit,
                article=produit.article,
                libelle=produit.nom,
                unite_libelle=str(produit.get_unite_vente_display()),
                quantite=ligne["quantite"],
                quantite_stock=ligne["quantite"] * (produit.conditionnement or 1),
                prix_unitaire_ttc=produit.prix_ttc,
                taux_tva=produit.taux_tva,
            )
        commande.recalculer()
        _prevenir_la_ferme(commande)
        commandes.append(commande)

    panier_service.vider(request)
    return commandes


def _fiche_client(utilisateur, exploitation):
    """La fiche client de cet acheteur chez cette ferme, si elle existe déjà."""
    if utilisateur is None:
        return None
    from client.models import Client

    return Client.objects.filter(user=utilisateur, exploitation=exploitation).first()


def _prevenir_la_ferme(commande):
    """Une commande qui dort sans que le paysan le sache est une vente perdue."""
    proprietaire = commande.exploitation.owner
    if proprietaire is None:
        return
    notify(
        proprietaire,
        type="commande",
        title=_("Nouvelle commande %(numero)s") % {"numero": commande.numero},
        message=_("%(acheteur)s a commandé pour %(montant)s €.")
        % {"acheteur": commande.acheteur_nom, "montant": commande.montant_ttc},
        priority="haute",
        action_url=f"/vente/commandes/{commande.pk}/",
    )


@transaction.atomic
def appliquer(commande, action, user=None):
    """Fait passer la commande d'un statut à l'autre, effets compris.

    Renvoie le message à afficher. Lève `CommandeRefusee` si la transition n'a
    pas de sens depuis le statut courant, ou si le stock manque au moment de
    servir.
    """
    depuis, vers = TRANSITIONS[action]
    if commande.statut not in depuis:
        raise CommandeRefusee(
            _("Une commande %(statut)s ne peut pas passer à cette étape.")
            % {"statut": commande.get_statut_display().lower()}
        )

    if vers == Commande.Statut.SERVIE:
        _sortir_du_stock(commande, user)
        # La vente entre au bilan maintenant, facturée ou non : un paysan qui
        # n'édite pas de facture pour ses particuliers doit quand même
        # retrouver son chiffre d'affaires.
        facturation.enregistrer_revenu(commande)

    commande.statut = vers
    champs = ["statut", "updated_at"]
    horodate = HORODATAGE.get(vers)
    if horodate:
        setattr(commande, horodate, timezone.now())
        champs.append(horodate)
    commande.save(update_fields=champs)
    return commande


def _sortir_du_stock(commande, user):
    """Écrit les sorties de dépôt : la marchandise quitte la ferme maintenant."""
    for ligne in commande.lignes.select_related("article"):
        if ligne.article is None or not ligne.quantite_stock:
            continue
        article = ligne.article
        if (article.quantite or 0) < ligne.quantite_stock:
            raise CommandeRefusee(
                _("Stock insuffisant pour « %(article)s » : %(reste)s en dépôt, %(demande)s à servir.")
                % {
                    "article": article.nom,
                    "reste": article.quantite or 0,
                    "demande": ligne.quantite_stock,
                }
            )
        Mouvement.objects.create(
            exploitation=commande.exploitation,
            article=article,
            type_mouvement=Mouvement.Type.SORTIE,
            motif=Mouvement.Motif.VENTE,
            quantite=ligne.quantite_stock,
            cout_unitaire=None,
            user=user,
            notes=_("Commande %(numero)s") % {"numero": commande.numero},
        )


def catalogue_reserve(exploitation):
    """Produits de la ferme dont une part est promise (pour l'écran commandes)."""
    return (
        Produit.objects.filter(exploitation=exploitation)
        .avec_reserve()
        .exclude(_reserve=0)
        .select_related("article")
    )
