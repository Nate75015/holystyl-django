"""Vues web Stock : articles, récoltes, mouvements et dépôts (tenant-scoped).

L'exploitation vient de `request.exploitation`, posée par
`core.middleware.CurrentExploitationMiddleware`.
"""

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from finances.models import Recolte
from parcelles.models import Parcelle

from . import recoltes as recoltes_service
from .models import Article, Depot, Mouvement, Unite

#: Pages sur lesquelles un formulaire peut demander à revenir. Le nom de vue
#: vient du POST : on ne redirige que vers ce qu'on connaît.
RETOURS = {"stock:articles", "stock:mouvements", "stock:depots", "stock:recoltes"}


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _retour(request, defaut):
    cible = request.POST.get("retour") or ""
    return redirect(cible if cible in RETOURS else defaut)


def _articles(request):
    exploitation = request.exploitation
    if exploitation is None:
        return Article.objects.none()
    return Article.objects.filter(exploitation=exploitation)


def _parcelles(request):
    exploitation = request.exploitation
    if exploitation is None:
        return Parcelle.objects.none()
    return Parcelle.objects.filter(exploitation=exploitation)


def _depots(request):
    exploitation = request.exploitation
    if exploitation is None:
        return Depot.objects.none()
    return Depot.objects.filter(exploitation=exploitation)


def _vide(valeur):
    """`None` → chaîne vide : un champ non renseigné doit revenir vide dans le
    formulaire, pas afficher « null »."""
    return "" if valeur is None else valeur


def _article_json(a):
    """Fiche article telle que la reprend le formulaire de modification."""
    return {
        "id": a.id,
        "nom": a.nom,
        "reference": a.reference,
        "categorie": a.categorie,
        "unite": a.unite,
        "depot": str(a.depot_id or ""),
        "seuil_alerte": _vide(a.seuil_alerte),
        "prix_unitaire": _vide(a.prix_unitaire),
        "fournisseur": a.fournisseur,
        "lot": a.lot,
        "date_peremption": a.date_peremption.isoformat() if a.date_peremption else "",
        "notes": a.notes,
    }


# ── Articles ────────────────────────────────────────────────────────

@login_required
def articles(request):
    base = _articles(request).select_related("depot")
    liste = list(base)

    en_alerte = [a for a in liste if a.en_alerte]
    valeur = sum(a.valeur for a in liste)

    return render(request, "stock/articles.html", {
        "articles": liste,
        "articles_json": [_article_json(a) for a in liste],
        "depots": _depots(request),
        "parcelles": _parcelles(request),
        "kpi_count": len(liste),
        "kpi_alerte": len(en_alerte),
        "kpi_valeur": round(valeur),
        "kpi_perimes": len([a for a in liste if a.perime]),
        "categories": Article.Categorie.choices,
        "unites": Unite.choices,
        "types_mouvement": Mouvement.Type.choices,
        "motifs": Mouvement.Motif.choices,
        "retour": "stock:articles",
        "page_title": _("Stock"),
    })


def _article_fields(request):
    return {
        "reference": (request.POST.get("reference") or "").strip(),
        "categorie": request.POST.get("categorie") or Article.Categorie.AUTRE,
        "unite": request.POST.get("unite") or Unite.KG,
        "seuil_alerte": _to_float(request.POST.get("seuil_alerte")),
        "prix_unitaire": _to_float(request.POST.get("prix_unitaire")),
        "fournisseur": (request.POST.get("fournisseur") or "").strip(),
        "lot": (request.POST.get("lot") or "").strip(),
        "date_peremption": _to_date(request.POST.get("date_peremption")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def article_save(request):
    """Crée un article, ou met à jour celui dont l'identifiant est posté.

    La quantité n'est modifiable qu'à la création : passé là, le stock ne bouge
    que par un mouvement, sans quoi le journal cesserait d'expliquer le niveau.
    """
    exploitation = request.exploitation
    nom = (request.POST.get("nom") or "").strip()
    if exploitation is None or not nom:
        messages.error(request, _("Indiquez la désignation de l'article."))
        return redirect("stock:articles")

    depot = _depots(request).filter(pk=request.POST.get("depot")).first()
    champs = _article_fields(request)

    identifiant = request.POST.get("id")
    if identifiant:
        article = get_object_or_404(Article, pk=identifiant, exploitation=exploitation)
        article.nom = nom
        article.depot = depot
        for champ, valeur in champs.items():
            setattr(article, champ, valeur)
        article.save()
        messages.success(request, _("Article mis à jour."))
        return redirect("stock:articles")

    article = Article.objects.create(exploitation=exploitation, nom=nom, depot=depot, **champs)
    # Le stock de départ passe par un mouvement : le journal doit pouvoir
    # justifier chaque unité présente, y compris celles du premier jour.
    initiale = _to_float(request.POST.get("quantite"), 0) or 0
    if initiale:
        Mouvement.objects.create(
            exploitation=exploitation,
            article=article,
            type_mouvement=Mouvement.Type.ENTREE,
            motif=Mouvement.Motif.INVENTAIRE,
            quantite=initiale,
            cout_unitaire=article.prix_unitaire,
            user=request.user,
            notes=_("Stock initial"),
        )
    messages.success(request, _("Article ajouté au stock."))
    return redirect("stock:articles")


@login_required
@require_POST
def article_delete(request, pk):
    get_object_or_404(Article, pk=pk, exploitation=request.exploitation).delete()
    return redirect("stock:articles")


# ── Mouvements ──────────────────────────────────────────────────────

@login_required
def mouvements(request):
    exploitation = request.exploitation
    base = (
        Mouvement.objects.filter(exploitation=exploitation).select_related("article", "parcelle")
        if exploitation
        else Mouvement.objects.none()
    )

    depuis = timezone.now() - timedelta(days=30)
    recents = base.filter(date__gte=depuis)
    achats = (
        recents.filter(type_mouvement=Mouvement.Type.ENTREE)
        .exclude(cout_unitaire=None)
        .aggregate(s=Sum("cout_unitaire"))["s"]
    )

    return render(request, "stock/mouvements.html", {
        "mouvements": base[:300],
        "articles": _articles(request),
        "parcelles": _parcelles(request),
        "kpi_count": base.count(),
        "kpi_entrees": recents.filter(type_mouvement=Mouvement.Type.ENTREE).count(),
        "kpi_sorties": recents.filter(type_mouvement=Mouvement.Type.SORTIE).count(),
        "kpi_achats": round(achats or 0),
        "types_mouvement": Mouvement.Type.choices,
        "motifs": Mouvement.Motif.choices,
        "retour": "stock:mouvements",
        "page_title": _("Mouvements de stock"),
    })


@login_required
@require_POST
def mouvement_create(request):
    exploitation = request.exploitation
    article = _articles(request).filter(pk=request.POST.get("article")).first()
    quantite = _to_float(request.POST.get("quantite"))
    type_mouvement = request.POST.get("type_mouvement") or Mouvement.Type.SORTIE

    if exploitation is None or article is None or quantite is None:
        messages.error(request, _("Choisissez un article et une quantité."))
        return _retour(request, "stock:mouvements")
    if quantite < 0 or (quantite == 0 and type_mouvement != Mouvement.Type.CORRECTION):
        messages.error(request, _("La quantité doit être positive."))
        return _retour(request, "stock:mouvements")

    # Une sortie plus grande que le stock est refusée plutôt que passée en
    # négatif : un stock négatif ne veut rien dire sur le terrain, et masquerait
    # une erreur de saisie derrière un chiffre d'apparence normale.
    if type_mouvement == Mouvement.Type.SORTIE and quantite > (article.quantite or 0):
        messages.error(request, _("Stock insuffisant : %(reste)s %(unite)s disponibles pour « %(article)s ».") % {
            "reste": article.quantite or 0,
            "unite": article.get_unite_display(),
            "article": article.nom,
        })
        return _retour(request, "stock:mouvements")

    Mouvement.objects.create(
        exploitation=exploitation,
        article=article,
        type_mouvement=type_mouvement,
        motif=request.POST.get("motif") or Mouvement.Motif.AUTRE,
        quantite=quantite,
        cout_unitaire=_to_float(request.POST.get("cout_unitaire")),
        parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first(),
        user=request.user,
        notes=(request.POST.get("notes") or "").strip(),
    )
    messages.success(request, _("Mouvement enregistré."))
    return _retour(request, "stock:mouvements")


# ── Récoltes ────────────────────────────────────────────────────────

@login_required
def recoltes(request):
    exploitation = request.exploitation
    base = (
        Recolte.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation
        else Recolte.objects.none()
    )
    liste = list(base[:300])

    # L'article qui a reçu chaque récolte, en une requête : le journal doit
    # dire où le lot est parti, pas seulement qu'il a été rentré.
    entrees = {
        m.recolte_id: m
        for m in Mouvement.objects.filter(recolte__in=liste).select_related("article")
    }
    for recolte in liste:
        recolte.entree = entrees.get(recolte.id)
        recolte.valorisation = round((recolte.quantite_kg or 0) * (recolte.prix_unitaire or 0), 2)

    total_kg = base.aggregate(s=Sum("quantite_kg"))["s"] or 0
    valorisation = sum(r.valorisation for r in liste)

    return render(request, "stock/recoltes.html", {
        "recoltes": liste,
        "articles": _articles(request).filter(categorie=Article.Categorie.RECOLTE),
        "parcelles": _parcelles(request),
        "depots": _depots(request),
        "kpi_count": base.count(),
        "kpi_kg": round(total_kg),
        "kpi_valeur": round(valorisation),
        "kpi_parcelles": base.values("parcelle").distinct().count(),
        "qualites": Recolte.Qualite.choices,
        "unites": recoltes_service.unites_possibles(),
        "retour": "stock:recoltes",
        "page_title": _("Récoltes"),
    })


@login_required
@require_POST
def recolte_create(request):
    """Déclare une récolte : elle entre en stock dans la foulée."""
    exploitation = request.exploitation
    if exploitation is None:
        messages.error(request, _("Créez d'abord votre exploitation."))
        return redirect("stock:recoltes")

    date = parse_datetime(request.POST.get("date") or "")
    if date and timezone.is_naive(date):
        date = timezone.make_aware(date)

    try:
        _recolte, mouvement = recoltes_service.enregistrer(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first(),
            quantite_kg=_to_float(request.POST.get("quantite_kg")),
            article=_articles(request).filter(pk=request.POST.get("article")).first(),
            nom_article=request.POST.get("nom_article") or "",
            unite=request.POST.get("unite") or Unite.KG,
            depot=_depots(request).filter(pk=request.POST.get("depot")).first(),
            qualite=request.POST.get("qualite") or Recolte.Qualite.CAT1,
            prix_unitaire=_to_float(request.POST.get("prix_unitaire")),
            cout_main_oeuvre=_to_float(request.POST.get("cout_main_oeuvre")),
            date=date,
            notes=(request.POST.get("notes") or "").strip(),
            user=request.user,
        )
    except recoltes_service.RecolteRefusee as refus:
        messages.error(request, str(refus))
        return _retour(request, "stock:recoltes")

    messages.success(request, _("Récolte rentrée : « %(article)s » passe à %(stock)s %(unite)s.") % {
        "article": mouvement.article.nom,
        "stock": mouvement.quantite_apres,
        "unite": mouvement.article.get_unite_display(),
    })
    return _retour(request, "stock:recoltes")


# ── Dépôts ──────────────────────────────────────────────────────────

@login_required
def depots(request):
    base = _depots(request).annotate(nb_articles=Count("articles"))
    liste = list(base.prefetch_related("articles"))
    for depot in liste:
        depot.valeur = round(sum(a.valeur for a in depot.articles.all()))

    sans_depot = _articles(request).filter(depot=None).count()

    return render(request, "stock/depots.html", {
        "depots": liste,
        "depots_json": [{
            "id": d.id, "nom": d.nom, "type_depot": d.type_depot,
            "localisation": d.localisation, "capacite": _vide(d.capacite),
            "unite_capacite": d.unite_capacite, "notes": d.notes,
        } for d in liste],
        "kpi_count": len(liste),
        "kpi_articles": sum(d.nb_articles for d in liste),
        "kpi_valeur": round(sum(d.valeur for d in liste)),
        "kpi_sans_depot": sans_depot,
        "types_depot": Depot.TypeDepot.choices,
        "unites": Unite.choices,
        "retour": "stock:depots",
        "page_title": _("Dépôts"),
    })


@login_required
@require_POST
def depot_save(request):
    exploitation = request.exploitation
    nom = (request.POST.get("nom") or "").strip()
    if exploitation is None or not nom:
        messages.error(request, _("Indiquez le nom du dépôt."))
        return redirect("stock:depots")

    champs = {
        "type_depot": request.POST.get("type_depot") or Depot.TypeDepot.HANGAR,
        "localisation": (request.POST.get("localisation") or "").strip(),
        "capacite": _to_float(request.POST.get("capacite")),
        "unite_capacite": request.POST.get("unite_capacite") or "",
        "notes": (request.POST.get("notes") or "").strip(),
    }

    identifiant = request.POST.get("id")
    if identifiant:
        depot = get_object_or_404(Depot, pk=identifiant, exploitation=exploitation)
        depot.nom = nom
        for champ, valeur in champs.items():
            setattr(depot, champ, valeur)
        depot.save()
    else:
        Depot.objects.create(exploitation=exploitation, nom=nom, **champs)
    return redirect("stock:depots")


@login_required
@require_POST
def depot_delete(request, pk):
    """Supprime un dépôt ; les articles qu'il portait restent, sans emplacement."""
    get_object_or_404(Depot, pk=pk, exploitation=request.exploitation).delete()
    return redirect("stock:depots")
