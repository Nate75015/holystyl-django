"""Vues web agronomie : référentiels cultures Kc / types de sol, saisons."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import CultureKc, Engrais, Fertigation, Saison, TypeSol


def _to_float(value, default):
    """Parse un nombre tolérant à la virgule décimale (ex. '0,30')."""
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


@login_required
def cultures(request):
    data = [
        {
            "id": c.id,
            "nom": c.nom,
            "sci": c.nom_scientifique,
            "cat": c.categorie,
            "catLabel": str(c.get_categorie_display()),
            "ki": c.kc_initial,
            "km": c.kc_mid,
            "ke": c.kc_end,
            "source": c.source,
        }
        for c in CultureKc.objects.all()
    ]
    return render(
        request,
        "agronomie/cultures.html",
        {
            "cultures_json": data,
            "categories": CultureKc.Categorie.choices,
            "page_title": _("Cultures & Kc"),
        },
    )


@login_required
@require_POST
def culture_create(request):
    """Crée une culture du référentiel depuis le formulaire « Nouvelle culture »."""
    nom = (request.POST.get("nom") or "").strip()
    if nom:
        CultureKc.objects.create(
            nom=nom,
            nom_scientifique=(request.POST.get("nom_scientifique") or "").strip(),
            categorie=request.POST.get("categorie") or CultureKc.Categorie.AUTRE,
            kc_initial=_to_float(request.POST.get("kc_initial"), 0.30),
            kc_mid=_to_float(request.POST.get("kc_mid"), 1.00),
            kc_end=_to_float(request.POST.get("kc_end"), 0.60),
            source=(request.POST.get("source") or "").strip() or "FAO-56",
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("agronomie:cultures")


@login_required
@require_POST
def culture_delete(request, pk):
    """Supprime une culture du référentiel."""
    CultureKc.objects.filter(pk=pk).delete()
    return redirect("agronomie:cultures")


@login_required
def types_sol(request):
    data = [
        {
            "id": t.id,
            "nom": t.nom,
            "texture": t.texture,
            "textureLabel": str(t.get_texture_display()),
            "retention": t.capacite_retention_mm,
            "ph": t.ph_typique,
            "conductivite": t.conductivite_hydraulique,
            "densite": t.densite_apparente,
        }
        for t in TypeSol.objects.all()
    ]
    return render(
        request,
        "agronomie/types_sol.html",
        {
            "types_json": data,
            "textures": TypeSol.Texture.choices,
            "page_title": _("Types de sol"),
        },
    )


@login_required
@require_POST
def type_sol_create(request):
    nom = (request.POST.get("nom") or "").strip()
    if nom:
        TypeSol.objects.create(
            nom=nom,
            texture=request.POST.get("texture") or TypeSol.Texture.LIMONEUX,
            capacite_retention_mm=_to_float(request.POST.get("retention"), 100),
            ph_typique=_to_float(request.POST.get("ph"), 7.0),
            conductivite_hydraulique=_to_float(request.POST.get("conductivite"), None),
            densite_apparente=_to_float(request.POST.get("densite"), None),
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("agronomie:types_sol")


@login_required
@require_POST
def type_sol_delete(request, pk):
    TypeSol.objects.filter(pk=pk).delete()
    return redirect("agronomie:types_sol")


@login_required
def saisons(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    qs = Saison.objects.filter(exploitation=exploitation) if exploitation else Saison.objects.none()
    return render(request, "agronomie/saisons.html", {"saisons": qs, "page_title": _("Saisons")})


PLAFOND_N = 170  # Directive Nitrates 91/676/CEE — kg N/ha/an en zone vulnérable


@login_required
def fertigation(request):
    """Catalogue d'engrais, suivi Directive Nitrates, historique des apports."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    fertigations = (
        Fertigation.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation
        else Fertigation.objects.none()
    )
    engrais = Engrais.objects.all()
    engrais_json = [
        {"nom": e.nom, "type": e.type_engrais, "n": e.n_pct, "p": e.p_pct, "k": e.k_pct}
        for e in engrais
    ]
    total_n = round(sum(f.azote_n or 0 for f in fertigations), 1)
    parcelles = Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
    return render(request, "agronomie/fertigation.html", {
        "engrais": engrais,
        "engrais_json": engrais_json,
        "fertigations": fertigations,
        "parcelles": parcelles,
        "total_n": total_n,
        "plafond_n": PLAFOND_N,
        "pct_n": min(100, round(total_n / PLAFOND_N * 100)) if PLAFOND_N else 0,
        "page_title": _("Fertigation"),
    })


@login_required
@require_POST
def fertigation_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if exploitation and parcelle:
        dt = parse_datetime(request.POST.get("date") or "") or timezone.now()
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        Fertigation.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            date=dt,
            produit=(request.POST.get("produit") or "").strip(),
            azote_n=_to_float(request.POST.get("azote_n"), 0),
            phosphore_p=_to_float(request.POST.get("phosphore_p"), 0),
            potassium_k=_to_float(request.POST.get("potassium_k"), 0),
            volume_l=_to_float(request.POST.get("volume_l"), 0),
        )
    return redirect("agronomie:fertigation")
