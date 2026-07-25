"""Vues web Élevage : référentiel animaux (familles → espèces → races)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Espece, Race


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _race_dict(r):
    """Sérialise une race (fiche détaillée)."""
    return {
        "id": r.id, "especeId": r.espece_id, "nom": r.nom, "sci": r.nom_scientifique,
        "photo": r.photo.url if r.photo else "",
        "description": r.description, "note": r.note, "nbAvis": r.nb_avis,
        "robe": r.robe, "poidsAdulte": r.poids_adulte, "taille": r.taille,
        "aptitude": r.aptitude, "prolificite": r.prolificite, "rusticite": r.rusticite,
        "alimentation": r.alimentation, "particularites": r.particularites,
        "conseilElevage": r.conseil_elevage,
        "origine": r.origine, "origineTexte": r.origine_texte,
    }


def _espece_dict(e):
    """Sérialise une espèce + ses races."""
    races = [_race_dict(r) for r in e.races.all()]
    return {
        "id": e.id, "nom": e.nom, "sci": e.nom_scientifique,
        "fam": e.famille, "famLabel": str(e.get_famille_display()),
        "prod": e.production, "prodLabel": str(e.get_production_display()),
        "gestation": e.duree_gestation_jours, "notes": e.notes,
        "races": races, "nbRaces": len(races),
    }


@login_required
def elevage(request):
    data = [_espece_dict(e) for e in Espece.objects.prefetch_related("races")]
    return render(
        request,
        "elevage/elevage.html",
        {
            "especes_json": data,
            "familles": Espece.Famille.choices,
            "productions": Espece.Production.choices,
            "page_title": _("Élevage"),
        },
    )


# ── Espèces ──────────────────────────────────────────────────────────────
def _espece_fields_from_post(request):
    g = request.POST.get
    return {
        "nom_scientifique": (g("nom_scientifique") or "").strip(),
        "famille": g("famille") or Espece.Famille.AUTRE,
        "production": g("production") or Espece.Production.MIXTE,
        "duree_gestation_jours": _to_int(g("duree_gestation_jours")),
        "notes": (g("notes") or "").strip(),
    }


@login_required
@require_POST
def espece_create(request):
    nom = (request.POST.get("nom") or "").strip()
    if nom:
        Espece.objects.create(nom=nom, **_espece_fields_from_post(request))
    return redirect("elevage:elevage")


@login_required
@require_POST
def espece_edit(request, pk):
    espece = Espece.objects.filter(pk=pk).first()
    nom = (request.POST.get("nom") or "").strip()
    if espece and nom:
        espece.nom = nom
        for field, value in _espece_fields_from_post(request).items():
            setattr(espece, field, value)
        espece.save()
    return redirect("elevage:elevage")


@login_required
@require_POST
def espece_delete(request, pk):
    Espece.objects.filter(pk=pk).delete()
    return redirect("elevage:elevage")


# ── Races ────────────────────────────────────────────────────────────────
def _race_fields_from_post(request):
    g = request.POST.get
    return {
        "nom_scientifique": (g("nom_scientifique") or "").strip(),
        "description": (g("description") or "").strip(),
        "note": _to_float(g("note")),
        "nb_avis": _to_int(g("nb_avis"), 0) or 0,
        "robe": (g("robe") or "").strip(),
        "poids_adulte": (g("poids_adulte") or "").strip(),
        "taille": (g("taille") or "").strip(),
        "aptitude": (g("aptitude") or "").strip(),
        "prolificite": (g("prolificite") or "").strip(),
        "rusticite": (g("rusticite") or "").strip(),
        "alimentation": (g("alimentation") or "").strip(),
        "particularites": (g("particularites") or "").strip(),
        "conseil_elevage": (g("conseil_elevage") or "").strip(),
        "origine": (g("origine") or "").strip(),
        "origine_texte": (g("origine_texte") or "").strip(),
    }


@login_required
@require_POST
def race_create(request):
    espece = Espece.objects.filter(pk=request.POST.get("espece")).first()
    nom = (request.POST.get("nom") or "").strip()
    if espece and nom:
        race = Race(espece=espece, nom=nom, **_race_fields_from_post(request))
        if request.FILES.get("photo"):
            race.photo = request.FILES["photo"]
        race.save()
    return redirect("elevage:elevage")


@login_required
@require_POST
def race_edit(request, pk):
    race = Race.objects.filter(pk=pk).first()
    nom = (request.POST.get("nom") or "").strip()
    if race and nom:
        race.nom = nom
        for field, value in _race_fields_from_post(request).items():
            setattr(race, field, value)
        if request.FILES.get("photo"):
            race.photo = request.FILES["photo"]
        race.save()
    return redirect("elevage:elevage")


@login_required
@require_POST
def race_delete(request, pk):
    Race.objects.filter(pk=pk).delete()
    return redirect("elevage:elevage")
