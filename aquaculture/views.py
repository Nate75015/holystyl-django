"""Vues web Aquaculture : installations et lots élevés (tenant-scoped)."""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .models import Bassin, EspeceAquacole, Lot, Souche


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace(" ", "").strip())
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


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _bassin_fields(request):
    """Champs d'une installation lus depuis le POST (création et édition)."""
    return {
        "type_bassin": request.POST.get("type_bassin") or Bassin.TypeBassin.BASSIN,
        "statut": request.POST.get("statut") or Bassin.Statut.EN_SERVICE,
        "source_eau": request.POST.get("source_eau") or "",
        "surface_m2": _to_float(request.POST.get("surface_m2")),
        "volume_m3": _to_float(request.POST.get("volume_m3")),
        "profondeur_m": _to_float(request.POST.get("profondeur_m")),
        "temperature_cible_c": _to_float(request.POST.get("temperature_cible_c")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


def _choix(bassin=None):
    return {
        "types": Bassin.TypeBassin.choices,
        "sources": Bassin.SourceEau.choices,
        "statuts": Bassin.Statut.choices,
        "statuts_lot": Lot.Statut.choices,
        "bassin": bassin,
    }


# ── Installations ───────────────────────────────────────────────────

@login_required
def bassins(request):
    exploitation = _exploitation(request)
    base = (
        Bassin.objects.filter(exploitation=exploitation).prefetch_related("lots")
        if exploitation else Bassin.objects.none()
    )

    volume = base.aggregate(s=Sum("volume_m3"))["s"] or 0
    biomasse = sum(bassin.biomasse_kg for bassin in base)
    lots_actifs = Lot.objects.filter(
        bassin__in=base, statut=Lot.Statut.EN_ELEVAGE
    ).count() if exploitation else 0

    return render(request, "aquaculture/bassins.html", {
        "bassins": base,
        "kpi_count": base.count(),
        "kpi_volume": round(volume),
        "kpi_lots": lots_actifs,
        "kpi_biomasse": round(biomasse),
        "page_title": _("Bassins"),
        **_choix(),
    })


@login_required
@require_POST
def bassin_create(request):
    exploitation = _exploitation(request)
    nom = (request.POST.get("nom") or "").strip()
    if exploitation and nom:
        bassin = Bassin.objects.create(exploitation=exploitation, nom=nom, **_bassin_fields(request))
        return redirect("aquaculture:detail", pk=bassin.pk)
    return redirect("aquaculture:bassins")


@login_required
def bassin_detail(request, pk):
    exploitation = _exploitation(request)
    bassin = get_object_or_404(Bassin, pk=pk, exploitation=exploitation)

    return render(request, "aquaculture/detail.html", {
        "lots": bassin.lots.all(),
        "page_title": bassin.nom,
        **_choix(bassin),
    })


@login_required
@require_POST
def bassin_edit(request, pk):
    exploitation = _exploitation(request)
    bassin = get_object_or_404(Bassin, pk=pk, exploitation=exploitation)

    nom = (request.POST.get("nom") or "").strip()
    if nom:
        for field, value in {"nom": nom, **_bassin_fields(request)}.items():
            setattr(bassin, field, value)
        bassin.save()
    return redirect("aquaculture:detail", pk=bassin.pk)


@login_required
@require_POST
def bassin_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(Bassin, pk=pk, exploitation=exploitation).delete()
    return redirect("aquaculture:bassins")


# ── Lots ────────────────────────────────────────────────────────────

@login_required
@require_POST
def lot_create(request, pk):
    exploitation = _exploitation(request)
    bassin = get_object_or_404(Bassin, pk=pk, exploitation=exploitation)

    espece = (request.POST.get("espece") or "").strip()
    if espece:
        Lot.objects.create(
            bassin=bassin,
            espece=espece,
            souche=(request.POST.get("souche") or "").strip(),
            effectif=_to_int(request.POST.get("effectif")),
            poids_moyen_g=_to_float(request.POST.get("poids_moyen_g")),
            date_mise_en_charge=_to_date(request.POST.get("date_mise_en_charge")),
            statut=request.POST.get("statut_lot") or Lot.Statut.EN_ELEVAGE,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("aquaculture:detail", pk=bassin.pk)


@login_required
@require_POST
def lot_delete(request, pk):
    exploitation = _exploitation(request)
    lot = get_object_or_404(Lot, pk=pk, bassin__exploitation=exploitation)
    bassin_pk = lot.bassin_id
    lot.delete()
    return redirect("aquaculture:detail", pk=bassin_pk)


# ── Référentiel : espèces aquacoles ─────────────────────────────────

def _souche_dict(s):
    """Sérialise une souche (fiche détaillée)."""
    return {
        "id": s.id, "especeId": s.espece_id, "nom": s.nom, "sci": s.nom_scientifique,
        "photo": s.photo.url if s.photo else "",
        "description": s.description, "note": s.note, "nbAvis": s.nb_avis,
        "livree": s.livree, "poidsAdulte": s.poids_adulte, "taille": s.taille,
        "aptitude": s.aptitude, "croissance": s.croissance, "rusticite": s.rusticite,
        "alimentation": s.alimentation, "particularites": s.particularites,
        "conseilElevage": s.conseil_elevage,
        "origine": s.origine, "origineTexte": s.origine_texte,
    }


def _espece_dict(e):
    """Sérialise une espèce + ses souches."""
    souches = [_souche_dict(s) for s in e.souches.all()]
    return {
        "id": e.id, "nom": e.nom, "sci": e.nom_scientifique,
        "fam": e.famille, "famLabel": str(e.get_famille_display()),
        "milieu": e.milieu, "milieuLabel": str(e.get_milieu_display()),
        "prod": e.production, "prodLabel": str(e.get_production_display()),
        "cycle": e.duree_cycle_jours, "temperature": e.temperature_optimale_c,
        "notes": e.notes,
        "souches": souches, "nbSouches": len(souches),
    }


@login_required
def especes(request):
    data = [_espece_dict(e) for e in EspeceAquacole.objects.prefetch_related("souches")]
    return render(request, "aquaculture/especes.html", {
        "especes_json": data,
        "familles": EspeceAquacole.Famille.choices,
        "milieux": EspeceAquacole.Milieu.choices,
        "productions": EspeceAquacole.Production.choices,
        "page_title": _("Espèces aquacoles"),
    })


def _espece_fields(request):
    g = request.POST.get
    return {
        "nom_scientifique": (g("nom_scientifique") or "").strip(),
        "famille": g("famille") or EspeceAquacole.Famille.AUTRE,
        "milieu": g("milieu") or EspeceAquacole.Milieu.DOUCE,
        "production": g("production") or EspeceAquacole.Production.CHAIR,
        "duree_cycle_jours": _to_int(g("duree_cycle_jours")),
        "temperature_optimale_c": _to_float(g("temperature_optimale_c")),
        "notes": (g("notes") or "").strip(),
    }


@login_required
@require_POST
def espece_create(request):
    nom = (request.POST.get("nom") or "").strip()
    if nom:
        EspeceAquacole.objects.create(nom=nom, **_espece_fields(request))
    return redirect("aquaculture:especes")


@login_required
@require_POST
def espece_edit(request, pk):
    espece = EspeceAquacole.objects.filter(pk=pk).first()
    nom = (request.POST.get("nom") or "").strip()
    if espece and nom:
        espece.nom = nom
        for field, value in _espece_fields(request).items():
            setattr(espece, field, value)
        espece.save()
    return redirect("aquaculture:especes")


@login_required
@require_POST
def espece_delete(request, pk):
    EspeceAquacole.objects.filter(pk=pk).delete()
    return redirect("aquaculture:especes")


# ── Référentiel : souches ───────────────────────────────────────────

def _souche_fields(request):
    g = request.POST.get
    return {
        "nom_scientifique": (g("nom_scientifique") or "").strip(),
        "description": (g("description") or "").strip(),
        "note": _to_float(g("note")),
        "nb_avis": _to_int(g("nb_avis"), 0) or 0,
        "livree": (g("livree") or "").strip(),
        "poids_adulte": (g("poids_adulte") or "").strip(),
        "taille": (g("taille") or "").strip(),
        "aptitude": (g("aptitude") or "").strip(),
        "croissance": (g("croissance") or "").strip(),
        "rusticite": (g("rusticite") or "").strip(),
        "alimentation": (g("alimentation") or "").strip(),
        "particularites": (g("particularites") or "").strip(),
        "conseil_elevage": (g("conseil_elevage") or "").strip(),
        "origine": (g("origine") or "").strip(),
        "origine_texte": (g("origine_texte") or "").strip(),
    }


@login_required
@require_POST
def souche_create(request):
    espece = EspeceAquacole.objects.filter(pk=request.POST.get("espece")).first()
    nom = (request.POST.get("nom") or "").strip()
    if espece and nom:
        souche = Souche(espece=espece, nom=nom, **_souche_fields(request))
        if request.FILES.get("photo"):
            souche.photo = request.FILES["photo"]
        souche.save()
    return redirect("aquaculture:especes")


@login_required
@require_POST
def souche_edit(request, pk):
    souche = Souche.objects.filter(pk=pk).first()
    nom = (request.POST.get("nom") or "").strip()
    if souche and nom:
        souche.nom = nom
        for field, value in _souche_fields(request).items():
            setattr(souche, field, value)
        if request.FILES.get("photo"):
            souche.photo = request.FILES["photo"]
        souche.save()
    return redirect("aquaculture:especes")


@login_required
@require_POST
def souche_delete(request, pk):
    Souche.objects.filter(pk=pk).delete()
    return redirect("aquaculture:especes")
