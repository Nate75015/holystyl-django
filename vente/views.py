"""Vues producteur : la boutique, le catalogue et les commandes reçues.

Les pages publiques vivent dans `vente.vitrine` : elles n'ont ni exploitation
courante ni utilisateur connecté, et n'ont donc rien à faire ici.
"""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from stock.models import Article

from . import commandes as commandes_service
from . import facturation
from .models import Boutique, Commande, Produit, slug_unique


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _coche(request, nom):
    return request.POST.get(nom) in ("1", "on", "true")


def boutique_de(request, creer=False):
    """La boutique de l'exploitation courante ; ouverte à la demande.

    Elle n'est créée qu'au premier passage sur ses réglages : une exploitation
    qui ne vend pas en direct n'a pas à traîner une vitrine vide.
    """
    exploitation = request.exploitation
    if exploitation is None:
        return None
    boutique = Boutique.objects.filter(exploitation=exploitation).first()
    if boutique is None and creer:
        boutique = Boutique.objects.create(exploitation=exploitation, titre=exploitation.name)
    return boutique


def _articles(request):
    exploitation = request.exploitation
    if exploitation is None:
        return Article.objects.none()
    return Article.objects.filter(exploitation=exploitation)


def _produits(request):
    exploitation = request.exploitation
    if exploitation is None:
        return Produit.objects.none()
    return Produit.objects.filter(exploitation=exploitation)


# ── Boutique ────────────────────────────────────────────────────────

@login_required
def boutique(request):
    """Réglages de la vitrine : identité, retrait, livraison, ouverture."""
    fiche = boutique_de(request)

    if request.method == "POST" and request.exploitation is not None:
        # Créée seulement ici, et *après* lecture du formulaire : la boutique
        # doit tirer son adresse publique du nom que le paysan vient de saisir,
        # pas de celui de l'exploitation qui n'est parfois qu'un sigle.
        if fiche is None:
            fiche = Boutique(exploitation=request.exploitation)
        fiche.titre = (request.POST.get("titre") or "").strip()
        fiche.accroche = (request.POST.get("accroche") or "").strip()
        fiche.description = (request.POST.get("description") or "").strip()
        fiche.est_ouverte = _coche(request, "est_ouverte")
        fiche.visible_marche = _coche(request, "visible_marche")
        fiche.retrait_ferme = _coche(request, "retrait_ferme")
        fiche.adresse_retrait = (request.POST.get("adresse_retrait") or "").strip()
        fiche.horaires_retrait = (request.POST.get("horaires_retrait") or "").strip()
        fiche.livraison = _coche(request, "livraison")
        fiche.rayon_livraison_km = _to_int(request.POST.get("rayon_livraison_km"))
        fiche.zone_livraison = (request.POST.get("zone_livraison") or "").strip()
        fiche.telephone = (request.POST.get("telephone") or "").strip()
        fiche.email = (request.POST.get("email") or "").strip()

        # L'adresse publique se corrige tant qu'on veut, mais jamais en double :
        # deux boutiques au même slug se voleraient leurs visiteurs.
        souhaite = (request.POST.get("slug") or "").strip()
        if souhaite:
            fiche.slug = slug_unique(Boutique, souhaite, exclure_pk=fiche.pk)
        fiche.save()
        messages.success(request, _("Boutique enregistrée."))
        return redirect("vente:boutique")

    return render(request, "vente/boutique.html", {
        "boutique": fiche,
        "nb_produits": _produits(request).count(),
        "nb_en_ligne": _produits(request).filter(statut=Produit.Statut.EN_LIGNE).count(),
        "page_title": _("Ma boutique"),
    })


# ── Catalogue ───────────────────────────────────────────────────────

@login_required
def produits(request):
    base = _produits(request).select_related("article")
    liste = list(base)

    return render(request, "vente/produits.html", {
        "produits": liste,
        "produits_json": [{
            "id": p.id, "nom": p.nom, "categorie": p.categorie,
            "article": str(p.article_id or ""), "unite_vente": p.unite_vente,
            "conditionnement": p.conditionnement, "prix_ttc": p.prix_ttc,
            "taux_tva": p.taux_tva, "quantite_min": p.quantite_min,
            "visible_marche": p.visible_marche, "description": p.description,
            "disponible_du": p.disponible_du.isoformat() if p.disponible_du else "",
            "disponible_au": p.disponible_au.isoformat() if p.disponible_au else "",
        } for p in liste],
        "boutique": boutique_de(request),
        "articles": _articles(request),
        "kpi_count": len(liste),
        "kpi_en_ligne": len([p for p in liste if p.statut == Produit.Statut.EN_LIGNE]),
        "kpi_epuises": len([p for p in liste if p.est_epuise]),
        "kpi_sans_stock": len([p for p in liste if p.article_id is None]),
        "categories": Produit.Categorie.choices,
        "unites_vente": Produit.UniteVente.choices,
        "page_title": _("Mes produits"),
    })


@login_required
@require_POST
def produit_save(request):
    exploitation = request.exploitation
    nom = (request.POST.get("nom") or "").strip()
    if exploitation is None or not nom:
        messages.error(request, _("Indiquez le nom du produit."))
        return redirect("vente:produits")

    champs = {
        "categorie": request.POST.get("categorie") or Produit.Categorie.AUTRE,
        "article": _articles(request).filter(pk=request.POST.get("article")).first(),
        "unite_vente": request.POST.get("unite_vente") or Produit.UniteVente.KG,
        "conditionnement": _to_float(request.POST.get("conditionnement"), 1) or 1,
        "prix_ttc": _to_float(request.POST.get("prix_ttc"), 0) or 0,
        "taux_tva": _to_float(request.POST.get("taux_tva"), 5.5),
        "quantite_min": _to_float(request.POST.get("quantite_min"), 1) or 1,
        "visible_marche": _coche(request, "visible_marche"),
        "description": (request.POST.get("description") or "").strip(),
        "disponible_du": _to_date(request.POST.get("disponible_du")),
        "disponible_au": _to_date(request.POST.get("disponible_au")),
    }

    identifiant = request.POST.get("id")
    if identifiant:
        produit = get_object_or_404(Produit, pk=identifiant, exploitation=exploitation)
        produit.nom = nom
        for champ, valeur in champs.items():
            setattr(produit, champ, valeur)
    else:
        produit = Produit(exploitation=exploitation, nom=nom, **champs)

    if request.FILES.get("photo"):
        produit.photo = request.FILES["photo"]
    produit.save()
    messages.success(request, _("Produit enregistré."))
    return redirect("vente:produits")


@login_required
@require_POST
def produit_publier(request, pk):
    """Met le produit en ligne — et ouvre la boutique si c'est le premier.

    Publier sans que la vitrine soit ouverte ne mettrait rien devant personne :
    le paysan croirait vendre alors que sa page reste invisible.
    """
    produit = get_object_or_404(Produit, pk=pk, exploitation=request.exploitation)
    if not produit.prix_ttc:
        messages.error(request, _("Fixez un prix avant de mettre « %(nom)s » en ligne.") % {"nom": produit.nom})
        return redirect("vente:produits")

    produit.statut = Produit.Statut.EN_LIGNE
    produit.save(update_fields=["statut", "updated_at"])

    fiche = boutique_de(request, creer=True)
    if not fiche.est_ouverte:
        fiche.est_ouverte = True
        fiche.save(update_fields=["est_ouverte", "updated_at"])
        messages.success(request, _("Votre boutique est ouverte : %(url)s") % {
            "url": request.build_absolute_uri(fiche.get_absolute_url()),
        })
    else:
        messages.success(request, _("« %(nom)s » est en ligne.") % {"nom": produit.nom})
    return redirect("vente:produits")


@login_required
@require_POST
def produit_retirer(request, pk):
    produit = get_object_or_404(Produit, pk=pk, exploitation=request.exploitation)
    produit.statut = Produit.Statut.RETIRE
    produit.save(update_fields=["statut", "updated_at"])
    return redirect("vente:produits")


@login_required
@require_POST
def produit_delete(request, pk):
    get_object_or_404(Produit, pk=pk, exploitation=request.exploitation).delete()
    return redirect("vente:produits")


# ── Commandes reçues ────────────────────────────────────────────────

@login_required
def commandes(request):
    exploitation = request.exploitation
    base = (
        Commande.objects.filter(exploitation=exploitation).prefetch_related("lignes")
        if exploitation
        else Commande.objects.none()
    )
    liste = list(base[:200])

    a_traiter = [c for c in liste if c.statut == Commande.Statut.NOUVELLE]
    en_cours = [c for c in liste if c.statut in (Commande.Statut.CONFIRMEE, Commande.Statut.PRETE)]
    servies = [c for c in liste if c.statut == Commande.Statut.SERVIE]

    return render(request, "vente/commandes.html", {
        "commandes": liste,
        "kpi_a_traiter": len(a_traiter),
        "kpi_en_cours": len(en_cours),
        "kpi_servies": len(servies),
        "kpi_ca": round(sum(c.montant_ttc for c in servies)),
        "statuts": Commande.Statut.choices,
        "page_title": _("Commandes"),
    })


@login_required
def commande_detail(request, pk):
    commande = get_object_or_404(
        Commande.objects.prefetch_related("lignes__article"),
        pk=pk, exploitation=request.exploitation,
    )
    return render(request, "vente/commande_detail.html", {
        "commande": commande,
        "lignes": commande.lignes.all(),
        # Ce que chaque étape autorise : les boutons de la page en découlent.
        "peut": {
            action: commande.statut in depuis
            for action, (depuis, _vers) in commandes_service.TRANSITIONS.items()
        },
        "facturable": commande.statut == Commande.Statut.SERVIE and commande.facture_id is None,
        "page_title": commande.numero,
    })


@login_required
@require_POST
def commande_transition(request, pk, action):
    """Fait avancer une commande — l'enchaînement permis vit dans le service."""
    if action not in commandes_service.TRANSITIONS:
        raise Http404
    commande = get_object_or_404(Commande, pk=pk, exploitation=request.exploitation)

    try:
        commandes_service.appliquer(commande, action, user=request.user)
    except commandes_service.CommandeRefusee as refus:
        messages.error(request, str(refus))
        return redirect("vente:commande_detail", pk=commande.pk)

    if action == "servir":
        messages.success(request, _("Commande %(numero)s servie : le stock est à jour.") % {"numero": commande.numero})
    else:
        messages.success(request, _("Commande %(numero)s : %(statut)s.") % {
            "numero": commande.numero, "statut": commande.get_statut_display().lower(),
        })
    return redirect("vente:commande_detail", pk=commande.pk)


@login_required
@require_POST
def commande_facturer(request, pk):
    """Émet la facture d'une commande remise (réutilise `finances`)."""
    commande = get_object_or_404(Commande, pk=pk, exploitation=request.exploitation)
    try:
        facture = facturation.facturer(commande)
    except facturation.FacturationRefusee as refus:
        messages.error(request, str(refus))
    else:
        messages.success(request, _("Facture %(numero)s créée pour la commande %(commande)s.") % {
            "numero": facture.numero, "commande": commande.numero,
        })
    return redirect("vente:commande_detail", pk=commande.pk)


# ── Espace acheteur ─────────────────────────────────────────────────

@login_required
def mes_commandes(request):
    """Ce qu'un acheteur retrouve de son côté : ses commandes et leur état.

    Le périmètre vient de ses fiches client, comme pour ses documents : on ne
    lit que ce qui le concerne, chez chaque ferme où il a un compte.
    """
    from client.models import Client

    fiches = Client.objects.filter(user=request.user)
    commandes_liees = (
        Commande.objects.filter(client_ref__in=fiches)
        .select_related("exploitation__boutique", "facture")
        .prefetch_related("lignes")
    )
    return render(request, "vente/mes_commandes.html", {
        "commandes": commandes_liees,
        "page_title": _("Mes commandes"),
    })
