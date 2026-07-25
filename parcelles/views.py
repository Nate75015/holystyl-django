"""Vues web parcelles : carte + liste, création, détail, édition, suppression, cadastre IGN."""

import json
import urllib.parse
import urllib.request

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .forms import ParcelleCampagneForm, ParcelleForm
from .models import Parcelle, ParcelleCampagne


def _exploitation_or_redirect(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
@ensure_csrf_cookie
def parcelle_list(request):
    exploitation = _exploitation_or_redirect(request)
    parcelles = (
        Parcelle.objects.filter(exploitation=exploitation).prefetch_related("analyses_sol")
        if exploitation else Parcelle.objects.none()
    )
    features, total_area = [], 0.0
    for p in parcelles:
        total_area += p.area or 0
        if p.boundaries:
            features.append({
                "type": "Feature",
                "geometry": p.boundaries,
                "properties": {"id": p.pk, "name": p.name, "area": p.area, "ref": p.cadastral_ref},
            })
    return render(request, "parcelles/list.html", {
        "parcelles": parcelles,
        "parcelles_geojson": {"type": "FeatureCollection", "features": features},
        "kpi_actives": parcelles.filter(status=Parcelle.Status.ACTIVE).count() if exploitation else 0,
        "kpi_total_area": round(total_area, 2),
        "needs_onboarding": exploitation is None,
        "page_title": _("Mes Parcelles"),
    })


@login_required
def parcelle_cadastre(request):
    """Proxy vers l'API Carto Cadastre (IGN) — parcelle(s) au point cliqué."""
    try:
        lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "lat/lon requis"}, status=400)
    geom = json.dumps({"type": "Point", "coordinates": [lon, lat]})
    url = "https://apicarto.ign.fr/api/cadastre/parcelle?geom=" + urllib.parse.quote(geom) + "&source_ign=PCI"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Holystyl/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return HttpResponse(resp.read(), content_type="application/json")
    except Exception as exc:  # noqa: BLE001 — toute erreur réseau/API renvoyée au front
        return JsonResponse({"error": str(exc)}, status=502)


def _create_parcelle_from_feature(exploitation, feature, name=None, lat=None, lon=None):
    """Crée une Parcelle depuis une feature cadastrale (API Carto IGN)."""
    geom = (feature or {}).get("geometry")
    if not geom:
        return None
    props = feature.get("properties", {})
    contenance = props.get("contenance")
    area = round(contenance / 10000, 4) if contenance else None
    ref = f"{props.get('section', '')} {props.get('numero', '')}".strip()
    commune = props.get("nom_com") or str(props.get("code_insee", "")) or str(props.get("code_com", ""))
    name = (name or "").strip() or f"Parcelle {ref}".strip() or "Parcelle"
    return Parcelle.objects.create(
        exploitation=exploitation,
        name=name[:255],
        boundaries=geom,
        cadastral_ref=ref[:50],
        commune=str(commune)[:100],
        area=area,
        official_area_ha=area,
        latitude=lat,
        longitude=lon,
        cadastre_data=props,          # toutes les données cadastre disponibles (brut IGN)
        acquired_at=timezone.now(),   # date d'acquisition
    )


@login_required
@require_POST
def parcelle_cadastre_save(request):
    """Enregistre une ou plusieurs parcelles sélectionnées depuis le cadastre IGN."""
    exploitation = _exploitation_or_redirect(request)
    if exploitation is None:
        # Crée une exploitation par défaut pour ne pas bloquer l'ajout de parcelles.
        exploitation = Exploitation.objects.create(
            owner=request.user,
            name=(getattr(request.user, "display_name", "") or "Mon exploitation")[:255],
        )
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"error": "JSON invalide"}, status=400)

    items = body.get("parcelles")
    if not items:  # rétrocompat : une seule parcelle
        items = [{"feature": body.get("feature"), "name": body.get("name"),
                  "lat": body.get("lat"), "lon": body.get("lon")}]

    created = 0
    for it in items:
        parcelle = _create_parcelle_from_feature(
            exploitation, it.get("feature"), it.get("name"), it.get("lat"), it.get("lon")
        )
        if parcelle:
            created += 1
    if not created:
        return JsonResponse({"error": "Aucune parcelle valide."}, status=400)
    return JsonResponse({"ok": True, "created": created})


@login_required
def parcelle_create(request):
    exploitation = _exploitation_or_redirect(request)
    if exploitation is None:
        messages.info(request, _("Configurez d'abord votre exploitation."))
        return redirect("exploitations:settings")

    if request.method == "POST":
        form = ParcelleForm(request.POST)
        campagne_form = ParcelleCampagneForm(request.POST)
        if form.is_valid() and campagne_form.is_valid():
            with transaction.atomic():
                parcelle = form.save(commit=False)
                parcelle.exploitation = exploitation
                parcelle.save()
                campagne = campagne_form.save(commit=False)
                campagne.parcelle = parcelle
                campagne.save()
            messages.success(request, _("Parcelle créée."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        form = ParcelleForm()
        campagne_form = ParcelleCampagneForm()

    return render(
        request,
        "parcelles/form.html",
        {"form": form, "campagne_form": campagne_form,
         "page_title": _("Nouvelle parcelle"), "is_create": True},
    )


@login_required
def parcelle_detail(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)

    center = None
    if parcelle.latitude is not None and parcelle.longitude is not None:
        center = [parcelle.latitude, parcelle.longitude]
    elif parcelle.boundaries:
        c = _bounds_center(parcelle.boundaries)
        if c:
            center = [c[0], c[1]]

    geojson = None
    if parcelle.boundaries:
        geojson = {
            "type": "Feature",
            "geometry": parcelle.boundaries,
            "properties": {"name": parcelle.name},
        }

    # Campagne affichée : celle demandée (?campagne=<id>), sinon la plus récente.
    campagnes = parcelle.campagnes.all()
    campagne = None
    sel_id = request.GET.get("campagne")
    if sel_id:
        campagne = campagnes.filter(pk=sel_id).first()
    if campagne is None:
        campagne = parcelle.campagne_courante

    return render(
        request,
        "parcelles/detail.html",
        {
            "parcelle": parcelle,
            "campagnes": campagnes,
            "campagne": campagne,
            "crop_stages": campagne.crop_stages.all() if campagne else [],
            "analyses_sol": parcelle.analyses_sol.all(),
            "geojson": geojson,
            "map_center": center,
            "page_title": parcelle.name,
        },
    )


@login_required
def campagne_create(request, parcelle_pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=parcelle_pk, exploitation=exploitation)
    if request.method == "POST":
        form = ParcelleCampagneForm(request.POST)
        form.instance.parcelle = parcelle
        if form.is_valid():
            campagne = form.save()
            messages.success(request, _("Campagne ajoutée."))
            return redirect(f"{parcelle.get_absolute_url()}?campagne={campagne.pk}")
    else:
        form = ParcelleCampagneForm()
    return render(request, "parcelles/campagne_form.html", {
        "form": form, "parcelle": parcelle, "page_title": _("Nouvelle campagne"),
    })


@login_required
def campagne_edit(request, pk):
    exploitation = _exploitation_or_redirect(request)
    campagne = get_object_or_404(ParcelleCampagne, pk=pk, parcelle__exploitation=exploitation)
    parcelle = campagne.parcelle
    if request.method == "POST":
        form = ParcelleCampagneForm(request.POST, instance=campagne)
        if form.is_valid():
            form.save()
            messages.success(request, _("Campagne mise à jour."))
            return redirect(f"{parcelle.get_absolute_url()}?campagne={campagne.pk}")
    else:
        form = ParcelleCampagneForm(instance=campagne)
    return render(request, "parcelles/campagne_form.html", {
        "form": form, "parcelle": parcelle, "campagne": campagne,
        "page_title": _("Modifier la campagne %(l)s") % {"l": campagne.libelle},
    })


@login_required
def campagne_delete(request, pk):
    exploitation = _exploitation_or_redirect(request)
    campagne = get_object_or_404(ParcelleCampagne, pk=pk, parcelle__exploitation=exploitation)
    parcelle = campagne.parcelle
    if request.method == "POST":
        campagne.delete()
        messages.success(request, _("Campagne supprimée."))
        return redirect("parcelles:detail", pk=parcelle.pk)
    return render(request, "parcelles/campagne_confirm_delete.html", {
        "campagne": campagne, "parcelle": parcelle,
    })


def _bounds_center(geom):
    """Centre (lat, lng) de la bounding-box d'une géométrie GeoJSON, ou None."""
    if not isinstance(geom, dict):
        return None
    lats, lngs = [], []
    stack = [geom.get("coordinates")]
    while stack:
        item = stack.pop()
        if isinstance(item, (list, tuple)):
            if len(item) >= 2 and all(isinstance(x, (int, float)) for x in item[:2]):
                lngs.append(item[0])
                lats.append(item[1])
            else:
                stack.extend(item)
    if not lats:
        return None
    return round((min(lats) + max(lats)) / 2, 6), round((min(lngs) + max(lngs)) / 2, 6)


@login_required
def parcelle_edit(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    campagne = parcelle.campagne_courante  # éditée en même temps que la parcelle
    if request.method == "POST":
        form = ParcelleForm(request.POST, instance=parcelle)
        campagne_form = ParcelleCampagneForm(request.POST, instance=campagne)
        campagne_form.instance.parcelle = parcelle
        if form.is_valid() and campagne_form.is_valid():
            with transaction.atomic():
                form.save()
                campagne_form.save()
            messages.success(request, _("Parcelle mise à jour."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        # Récupère lat/lng depuis le polygone cadastre si elles manquent.
        if parcelle.latitude is None and parcelle.longitude is None and parcelle.boundaries:
            center = _bounds_center(parcelle.boundaries)
            if center:
                parcelle.latitude, parcelle.longitude = center
                parcelle.save(update_fields=["latitude", "longitude"])
        form = ParcelleForm(instance=parcelle)
        campagne_form = ParcelleCampagneForm(instance=campagne)
    return render(
        request,
        "parcelles/form.html",
        {"form": form, "campagne_form": campagne_form, "parcelle": parcelle,
         "page_title": _("Modifier %(n)s") % {"n": parcelle.name}},
    )


@login_required
def parcelle_delete(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        parcelle.delete()
        messages.success(request, _("Parcelle supprimée."))
        return redirect("parcelles:list")
    return render(request, "parcelles/confirm_delete.html", {"parcelle": parcelle})
