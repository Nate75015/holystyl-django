"""Pages publiques : la place de marché et les boutiques de ferme.

Ces vues n'ont ni utilisateur connecté ni exploitation courante : le périmètre
vient du slug de la boutique, jamais de `request.exploitation`. Elles ne
montrent que ce qui est doublement consenti — la boutique ouverte, le produit
en ligne (`Produit.objects.publiables()`).
"""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import commandes as commandes_service
from . import panier as panier_service
from .models import Boutique, Commande, Produit


def _catalogue_marche(request):
    """Les produits de la place de marché, filtrés par la recherche."""
    produits = (
        Produit.objects.sur_le_marche()
        .avec_reserve()
        .select_related("exploitation", "exploitation__boutique", "article")
    )

    recherche = (request.GET.get("q") or "").strip()
    if recherche:
        produits = produits.filter(
            Q(nom__icontains=recherche)
            | Q(description__icontains=recherche)
            | Q(exploitation__boutique__titre__icontains=recherche)
            | Q(exploitation__name__icontains=recherche)
            | Q(exploitation__city__icontains=recherche)
        )
    return produits, recherche


def _familles(produits):
    """Toutes les catégories du catalogue, avec ce que chacune contient.

    Toutes, y compris les vides : un filtre absent laisse croire que la
    catégorie n'existe pas, quand elle est seulement sans offre aujourd'hui.
    Les vides sont affichées en retrait et le disent par leur zéro.
    """
    comptes = dict(
        Produit.objects.sur_le_marche().values_list("categorie").annotate(n=Count("id"))
    )
    return [
        {"cle": cle, "label": libelle, "n": comptes.get(cle, 0)}
        for cle, libelle in Produit.Categorie.choices
    ]


def marche(request, categorie=""):
    """Place de marché : tout ce que les fermes ouvertes proposent."""
    produits, recherche = _catalogue_marche(request)
    if categorie and categorie in Produit.Categorie.values:
        produits = produits.filter(categorie=categorie)
    elif categorie:
        categorie = ""  # clé inconnue : on retombe sur le marché entier

    liste = list(produits[:120])
    fermes = {p.exploitation_id for p in liste}

    return render(request, "vente/marche.html", {
        "produits": liste,
        "familles": _familles(produits),
        "categorie": categorie,
        "categorie_label": dict(Produit.Categorie.choices).get(categorie, ""),
        "recherche": recherche,
        "nb_fermes": len(fermes),
        "panier_nb": panier_service.nombre(request),
        "layout_public": True,
        "page_title": _("Le marché des fermes"),
    })


def boutique_publique(request, slug):
    """La vitrine d'une ferme : sa présentation et son catalogue."""
    boutique = get_object_or_404(
        Boutique.objects.select_related("exploitation"), slug=slug, est_ouverte=True
    )
    produits = list(
        Produit.objects.publiables()
        .avec_reserve()
        .filter(exploitation=boutique.exploitation)
        .select_related("article")
    )

    # Regroupement par famille, dans l'ordre d'apparition du catalogue : une
    # page de ferme se parcourt par rayons, pas comme une liste à plat.
    libelles = dict(Produit.Categorie.choices)
    rayons = {}
    for produit in produits:
        rayons.setdefault(produit.categorie, []).append(produit)

    return render(request, "vente/boutique_publique.html", {
        "boutique": boutique,
        "exploitation": boutique.exploitation,
        "rayons": [
            {"label": libelles.get(cle, cle), "produits": lot}
            for cle, lot in sorted(rayons.items(), key=lambda item: str(libelles.get(item[0], "")))
        ],
        "nb_produits": len(produits),
        "panier_nb": panier_service.nombre(request),
        "layout_public": True,
        "page_title": boutique.nom,
    })


def produit_public(request, slug, produit_slug):
    """Fiche d'un produit. En T2, la vente se conclut en contactant la ferme."""
    boutique = get_object_or_404(
        Boutique.objects.select_related("exploitation"), slug=slug, est_ouverte=True
    )
    produit = get_object_or_404(
        Produit.objects.publiables().avec_reserve().select_related("article"),
        exploitation=boutique.exploitation, slug=produit_slug,
    )
    autres = (
        Produit.objects.publiables()
        .filter(exploitation=boutique.exploitation)
        .exclude(pk=produit.pk)[:6]
    )

    return render(request, "vente/produit_public.html", {
        "boutique": boutique,
        "exploitation": boutique.exploitation,
        "produit": produit,
        "autres": autres,
        "panier_nb": panier_service.nombre(request),
        "layout_public": True,
        "page_title": f"{produit.nom} — {boutique.nom}",
    })


# ── Panier ──────────────────────────────────────────────────────────

def _retour_sur(request, defaut="vente:panier"):
    """Renvoie l'acheteur d'où il vient, sans jamais quitter le site."""
    cible = request.POST.get("retour") or ""
    if cible and url_has_allowed_host_and_scheme(cible, allowed_hosts={request.get_host()},
                                                 require_https=request.is_secure()):
        return redirect(cible)
    return redirect(defaut)


def panier(request):
    groupes = panier_service.groupes(request)
    return render(request, "vente/panier.html", {
        "groupes": groupes,
        "total": panier_service.total(groupes),
        "panier_nb": panier_service.nombre(request),
        "layout_public": True,
        "page_title": _("Mon panier"),
    })


@require_POST
def panier_ajouter(request):
    produit = get_object_or_404(Produit.objects.publiables(), pk=request.POST.get("produit"))
    quantite = _quantite(request.POST.get("quantite"), produit.quantite_min or 1)

    disponible = produit.disponible
    if disponible is not None and disponible <= 0:
        messages.error(request, _("« %(nom)s » est épuisé.") % {"nom": produit.nom})
        return _retour_sur(request, produit.get_absolute_url())
    if disponible is not None:
        quantite = min(quantite, disponible)

    panier_service.ajouter(request, produit.pk, quantite)
    messages.success(request, _("« %(nom)s » ajouté au panier.") % {"nom": produit.nom})
    return _retour_sur(request)


@require_POST
def panier_ligne(request, produit_id):
    """Change la quantité d'une ligne, ou la retire (quantité vide ou nulle)."""
    panier_service.definir(request, produit_id, _quantite(request.POST.get("quantite"), 0))
    return redirect("vente:panier")


def _quantite(valeur, defaut):
    try:
        return max(0, float(str(valeur).replace(",", ".")))
    except (TypeError, ValueError):
        return defaut


def commander(request):
    """Coordonnées et créneau, puis une commande par ferme."""
    groupes = panier_service.groupes(request)
    if not groupes:
        return redirect("vente:panier")

    saisie = {}
    if request.method == "POST":
        saisie = {champ: (request.POST.get(champ) or "").strip() for champ in (
            "nom", "email", "telephone", "creneau", "notes", "adresse_livraison", "mode_retrait", "date_souhaitee",
        )}
        try:
            creees = commandes_service.creer_depuis_panier(
                request,
                nom=saisie["nom"], email=saisie["email"], telephone=saisie["telephone"],
                mode_retrait=saisie["mode_retrait"] or Commande.Retrait.FERME,
                adresse_livraison=saisie["adresse_livraison"],
                date_souhaitee=parse_date(saisie["date_souhaitee"] or ""),
                creneau=saisie["creneau"], notes=saisie["notes"],
            )
        except commandes_service.CommandeRefusee as refus:
            messages.error(request, str(refus))
        else:
            # Un panier multi-fermes donne plusieurs commandes : l'acheteur doit
            # pouvoir les suivre toutes, pas seulement la première.
            request.session["dernieres_commandes"] = [str(c.jeton) for c in creees]
            return redirect(creees[0].get_absolute_url())

    return render(request, "vente/commander.html", {
        "groupes": groupes,
        "total": panier_service.total(groupes),
        "panier_nb": panier_service.nombre(request),
        "saisie": saisie,
        "modes_retrait": Commande.Retrait.choices,
        "layout_public": True,
        "page_title": _("Valider ma commande"),
    })


def suivi(request, jeton):
    """Suivi d'une commande par son lien : l'acheteur n'a pas de compte."""
    commande = get_object_or_404(
        Commande.objects.select_related("exploitation", "exploitation__boutique").prefetch_related("lignes"),
        jeton=jeton,
    )
    autres = [
        c for c in Commande.objects.filter(jeton__in=request.session.get("dernieres_commandes") or [])
        .select_related("exploitation__boutique")
        if c.pk != commande.pk
    ]

    etapes = [
        (Commande.Statut.NOUVELLE, _("Reçue"), commande.created_at),
        (Commande.Statut.CONFIRMEE, _("Confirmée par la ferme"), commande.confirmee_le),
        (Commande.Statut.PRETE, _("Prête"), commande.prete_le),
        (Commande.Statut.SERVIE, _("Remise"), commande.servie_le),
    ]

    return render(request, "vente/suivi.html", {
        "commande": commande,
        "boutique": getattr(commande.exploitation, "boutique", None),
        "lignes": commande.lignes.all(),
        "etapes": [{"cle": cle, "label": label, "le": le} for cle, label, le in etapes],
        "autres": autres,
        "panier_nb": panier_service.nombre(request),
        "layout_public": True,
        "page_title": commande.numero,
    })
