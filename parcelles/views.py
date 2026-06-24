"""Vues web parcelles : carte + liste, création, détail, édition, suppression, cadastre IGN."""

import json
import urllib.parse
import urllib.request

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .forms import ParcelleForm
from .models import Parcelle


def _exploitation_or_redirect(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def parcelle_list(request):
    exploitation = _exploitation_or_redirect(request)
    parcelles = (
        Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
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


@login_required
@require_POST
def parcelle_cadastre_save(request):
    """Enregistre une parcelle sélectionnée depuis le cadastre IGN."""
    exploitation = _exploitation_or_redirect(request)
    if exploitation is None:
        return JsonResponse({"error": "Configurez votre exploitation."}, status=400)
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"error": "JSON invalide"}, status=400)
    feature = body.get("feature") or {}
    geom = feature.get("geometry")
    if not geom:
        return JsonResponse({"error": "Géométrie manquante"}, status=400)
    props = feature.get("properties", {})
    contenance = props.get("contenance")
    area = round(contenance / 10000, 4) if contenance else None
    ref = f"{props.get('section', '')} {props.get('numero', '')}".strip()
    commune = props.get("nom_com") or str(props.get("code_insee", "")) or str(props.get("code_com", ""))
    name = (body.get("name") or "").strip() or (f"Parcelle {ref}".strip())
    parcelle = Parcelle.objects.create(
        exploitation=exploitation,
        name=name[:255] or "Parcelle",
        boundaries=geom,
        cadastral_ref=ref[:50],
        commune=str(commune)[:100],
        area=area,
        official_area_ha=area,
        latitude=body.get("lat"),
        longitude=body.get("lon"),
    )
    return JsonResponse({"ok": True, "id": parcelle.pk, "name": parcelle.name, "area": parcelle.area})


@login_required
def parcelle_create(request):
    exploitation = _exploitation_or_redirect(request)
    if exploitation is None:
        messages.info(request, _("Configurez d'abord votre exploitation."))
        return redirect("exploitations:settings")

    if request.method == "POST":
        form = ParcelleForm(request.POST)
        if form.is_valid():
            parcelle = form.save(commit=False)
            parcelle.exploitation = exploitation
            parcelle.save()
            messages.success(request, _("Parcelle créée."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        form = ParcelleForm()

    return render(
        request,
        "parcelles/form.html",
        {"form": form, "page_title": _("Nouvelle parcelle"), "is_create": True},
    )


@login_required
def parcelle_detail(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    return render(
        request,
        "parcelles/detail.html",
        {"parcelle": parcelle, "page_title": parcelle.name},
    )


@login_required
def parcelle_edit(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = ParcelleForm(request.POST, instance=parcelle)
        if form.is_valid():
            form.save()
            messages.success(request, _("Parcelle mise à jour."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        form = ParcelleForm(instance=parcelle)
    return render(
        request,
        "parcelles/form.html",
        {"form": form, "parcelle": parcelle, "page_title": _("Modifier %(n)s") % {"n": parcelle.name}},
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
