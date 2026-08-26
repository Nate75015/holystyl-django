"""Panier d'achat, tenu en session.

L'acheteur n'a pas de compte : son panier vit dans sa session, pas en base —
rien à purger, rien à rattacher. Il peut mêler plusieurs fermes ; c'est la
validation qui le scindera, parce qu'on ne retire pas une commande dans deux
cours de ferme à la fois.
"""

from .models import Produit

CLE = "panier"


def lire(request):
    """Le panier brut : {identifiant de produit (str) : quantité}."""
    return dict(request.session.get(CLE) or {})


def _ecrire(request, contenu):
    request.session[CLE] = contenu
    request.session.modified = True


def definir(request, produit_id, quantite):
    """Fixe la quantité d'un produit ; 0 ou moins le retire."""
    contenu = lire(request)
    cle = str(produit_id)
    if quantite and quantite > 0:
        contenu[cle] = float(quantite)
    else:
        contenu.pop(cle, None)
    _ecrire(request, contenu)


def ajouter(request, produit_id, quantite=1):
    contenu = lire(request)
    cle = str(produit_id)
    definir(request, produit_id, contenu.get(cle, 0) + (quantite or 1))


def vider(request):
    request.session.pop(CLE, None)
    request.session.modified = True


def nombre(request):
    """Nombre d'articles dans le panier, pour la pastille de l'entête."""
    return len(lire(request))


def groupes(request):
    """Le panier rangé par ferme, avec ses totaux.

    Un produit devenu invisible (retiré, boutique fermée, hors saison) est
    silencieusement sorti du panier : le proposer encore mènerait à une
    commande que la ferme ne peut pas honorer.
    """
    contenu = lire(request)
    if not contenu:
        return []

    produits = (
        Produit.objects.publiables()
        .avec_reserve()
        .filter(pk__in=[k for k in contenu if str(k).isdigit()])
        .select_related("exploitation", "exploitation__boutique", "article")
    )
    connus = {str(p.pk): p for p in produits}
    if set(connus) != set(contenu):
        _ecrire(request, {cle: q for cle, q in contenu.items() if cle in connus})

    par_ferme = {}
    for cle, produit in connus.items():
        quantite = float(contenu[cle])
        groupe = par_ferme.setdefault(produit.exploitation_id, {
            "exploitation": produit.exploitation,
            "boutique": produit.exploitation.boutique,
            "lignes": [],
            "total": 0,
        })
        montant = round(quantite * produit.prix_ttc, 2)
        groupe["lignes"].append({"produit": produit, "quantite": quantite, "montant": montant})
        groupe["total"] = round(groupe["total"] + montant, 2)

    for groupe in par_ferme.values():
        groupe["lignes"].sort(key=lambda ligne: ligne["produit"].nom)
    return sorted(par_ferme.values(), key=lambda g: g["boutique"].nom)


def total(groupes_panier):
    return round(sum(g["total"] for g in groupes_panier), 2)
