"""De la commande servie à l'argent : le revenu, puis la facture.

Deux gestes distincts, et c'est voulu :

* le **revenu** s'enregistre à la remise, sans rien demander — un paysan qui ne
  facture pas ses particuliers doit quand même retrouver sa vente dans son
  bilan économique ;
* la **facture** ne se crée que si on la demande. Elle réutilise `finances`
  telle quelle : même numérotation (règle BR-FR-01), même structure de lignes,
  donc même export UBL et même dépôt SUPER PDP pour les professionnels.

Les prix de la boutique sont TTC (c'est ce que voit l'acheteur), une facture se
construit en HT plus TVA : la conversion se fait ici, ligne par ligne, chaque
ligne gardant son propre taux.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from finances import services as finances_services
from finances import ubl
from finances.models import Facture, Revenu

from .models import Commande, Produit

#: Codes d'unité UBL (UN/ECE 20). Hors poids et volume, la pièce fait l'affaire.
UNITE_UBL = {"kg": "KGM", "litre": "LTR"}

#: À quelle famille de revenus rattacher la vente, d'après ce qui a été vendu.
CATEGORIE_REVENU = {
    Produit.Categorie.LEGUME: Revenu.Categorie.VENTE_LEGUMES,
    Produit.Categorie.FRUIT: Revenu.Categorie.VENTE_FRUITS,
    Produit.Categorie.CEREALE: Revenu.Categorie.VENTE_CEREALES,
    Produit.Categorie.FARINE: Revenu.Categorie.VENTE_CEREALES,
}


class FacturationRefusee(ValueError):
    """Facture qu'on ne peut pas émettre, avec le motif pour le paysan."""


def _categorie_revenu(commande):
    """La famille du produit qui pèse le plus dans la commande."""
    poids = {}
    for ligne in commande.lignes.all():
        if ligne.produit is None:
            continue
        poids[ligne.produit.categorie] = poids.get(ligne.produit.categorie, 0) + ligne.montant_ttc
    if not poids:
        return Revenu.Categorie.AUTRE
    dominante = max(poids, key=poids.get)
    return CATEGORIE_REVENU.get(dominante, Revenu.Categorie.AUTRE)


def enregistrer_revenu(commande):
    """Inscrit la vente au bilan économique, au moment de la remise.

    Le montant retenu est le HT : la TVA collectée n'est pas un revenu de la
    ferme, elle est due à l'État.
    """
    return Revenu.objects.create(
        exploitation=commande.exploitation,
        date=timezone.now(),
        categorie=_categorie_revenu(commande),
        montant=commande.montant_ht,
        description=_("Vente directe — commande %(numero)s") % {"numero": commande.numero},
        acheteur=commande.acheteur_nom[:255],
    )


def _fiche_client(commande):
    """La fiche client de l'acheteur, créée au besoin.

    Une facture désigne quelqu'un : l'acheteur venu de la vitrine n'a souvent
    aucune fiche, et c'est la facturation qui le fait entrer dans le fichier
    clients de la ferme — pas la commande, qui peut n'aboutir jamais.
    """
    from client.models import Client

    if commande.client_ref is not None:
        return commande.client_ref

    fiche = Client.objects.create(
        exploitation=commande.exploitation,
        nom=commande.acheteur_nom,
        categorie=Client.Categorie.PARTICULIER,
        statut=Client.Statut.ACTIF,
        email=commande.acheteur_email,
        telephone=commande.acheteur_telephone,
    )
    commande.client_ref = fiche
    commande.save(update_fields=["client_ref", "updated_at"])
    return fiche


def lignes_facture(commande):
    """Les lignes de la commande converties en lignes de facture (HT + taux)."""
    lignes = []
    for ligne in commande.lignes.all():
        taux = ligne.taux_tva or 0
        prix_ht = round(ligne.prix_unitaire_ttc / (1 + taux / 100), 2)
        lignes.append({
            "designation": ligne.libelle,
            "quantite": ligne.quantite,
            "prix_unitaire": prix_ht,
            "unite": UNITE_UBL.get(
                ligne.produit.unite_vente if ligne.produit else "", "C62"
            ),
            "taux_tva": taux,
            "montant": round(ligne.quantite * prix_ht, 2),
        })
    return lignes


def taux_dominant(lignes):
    """Le taux qui porte le plus gros montant — le champ document n'en tient qu'un.

    `finances.ubl` calcule la TVA ligne par ligne et regroupe les sous-totaux
    par taux : une commande mêlant légumes à 5,5 % et vin à 20 % sort juste.
    Ce champ ne sert qu'à l'affichage d'un taux unique quand il y en a un.
    """
    poids = {}
    for ligne in lignes:
        poids[ligne["taux_tva"]] = poids.get(ligne["taux_tva"], 0) + ligne["montant"]
    return max(poids, key=poids.get) if poids else 0


@transaction.atomic
def facturer(commande):
    """Émet la facture d'une commande remise. Renvoie la `finances.Facture`."""
    if commande.statut != Commande.Statut.SERVIE:
        raise FacturationRefusee(
            _("On ne facture qu'une commande remise : « %(statut)s » pour l'instant.")
            % {"statut": commande.get_statut_display()}
        )
    if commande.facture_id is not None:
        raise FacturationRefusee(
            _("La commande %(numero)s est déjà facturée (%(facture)s).")
            % {"numero": commande.numero, "facture": commande.facture.numero}
        )

    fiche = _fiche_client(commande)
    lignes = lignes_facture(commande)
    if not lignes:
        raise FacturationRefusee(_("Cette commande n'a aucune ligne à facturer."))

    professionnel = fiche.categorie == fiche.Categorie.PROFESSIONNEL
    facture = Facture(
        exploitation=commande.exploitation,
        numero=finances_services.prochain_numero(commande.exploitation),
        client_ref=fiche,
        client_nom=fiche.nom_complet,
        date_emission=timezone.now(),
        lignes=lignes,
        taux_tva=taux_dominant(lignes),
        # Vente directe : le particulier a réglé au retrait, la facture ne fait
        # que constater. Un professionnel, lui, paie à réception : sa facture
        # reste due tant qu'il n'a pas payé.
        statut=Facture.Statut.EN_ATTENTE if professionnel else Facture.Statut.PAYEE,
        notes=_("Vente directe — commande %(numero)s") % {"numero": commande.numero},
    )
    ht, tva = ubl.totaux_lignes(facture)
    facture.montant_ht = float(ht)
    facture.montant_tva = float(tva)
    facture.montant_ttc = float(ht + tva)
    facture.save()

    commande.facture = facture
    commande.save(update_fields=["facture", "updated_at"])
    return facture
