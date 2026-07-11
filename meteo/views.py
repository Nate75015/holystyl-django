"""Vues web Météo : index (toutes les villes) + détail par ville, historique, capture."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import ReleveMeteo, VilleMeteo
from .scheduler import run_scheduled_captures
from .services import fetch_current, fetch_weather, geocode

_DEFAULT_LAT, _DEFAULT_LON = 43.95, 4.81  # Avignon par défaut


def _exploitation(request, create=False):
    exp = Exploitation.objects.filter(owner=request.user).first()
    if exp is None and create:
        exp = Exploitation.objects.create(
            owner=request.user,
            name=(getattr(request.user, "full_name", "") or "Mon exploitation")[:255],
        )
    return exp


def _home_location(request, exploitation):
    """Localisation par défaut de l'exploitation (sinon parcelle, sinon Avignon)."""
    if exploitation and exploitation.latitude is not None and exploitation.longitude is not None:
        return exploitation.latitude, exploitation.longitude, (exploitation.city or exploitation.name)
    parcelle = (
        Parcelle.objects.filter(exploitation=exploitation, latitude__isnull=False).first()
        if exploitation else None
    )
    if parcelle:
        return parcelle.latitude, parcelle.longitude, (parcelle.commune or parcelle.name)
    return _DEFAULT_LAT, _DEFAULT_LON, "Avignon"


def _with_current(villes):
    for v in villes:
        try:
            cw = fetch_current(v.latitude, v.longitude)
            v.temp, v.icon, v.label = cw["temp"], cw["icon"], cw["label"]
        except Exception:  # noqa: BLE001 — météo ville indisponible
            v.temp, v.icon, v.label = None, "help_outline", ""
    return villes


@login_required
def meteo_index(request):
    """Vue d'ensemble : toutes les villes enregistrées + lieu de l'exploitation."""
    exploitation = _exploitation(request)
    villes = _with_current(list(VilleMeteo.objects.filter(exploitation=exploitation))) if exploitation else []

    hlat, hlon, hloc = _home_location(request, exploitation)
    home = {"nom": hloc, "lat": round(hlat, 4), "lon": round(hlon, 4), "slug": slugify(hloc) or "exploitation"}
    try:
        cw = fetch_current(hlat, hlon)
        home.update(temp=cw["temp"], icon=cw["icon"], label=cw["label"])
    except Exception:  # noqa: BLE001
        home.update(temp=None, icon="help_outline", label="")

    return render(request, "meteo/index.html", {
        "villes": villes,
        "home": home,
        "page_title": _("Météo"),
    })


@login_required
@require_POST
def capture_config(request, slug):
    """Définit la capture automatique d'une ville (activation + fréquence)."""
    exploitation = _exploitation(request, create=True)
    ville = get_object_or_404(VilleMeteo, slug=slug, exploitation=exploitation)
    ville.capture_auto = request.POST.get("enabled") == "on"
    try:
        ville.capture_frequence = int(request.POST.get("frequence") or VilleMeteo.Frequence.QUOTIDIEN)
    except (ValueError, TypeError):
        ville.capture_frequence = VilleMeteo.Frequence.QUOTIDIEN
    ville.save(update_fields=["capture_auto", "capture_frequence"])
    messages.success(request, _("Capture automatique mise à jour."))
    return redirect("meteo:detail", slug=slug)


@login_required
def meteo_detail(request, slug):
    """Météo détaillée d'une ville (enregistrée, ou géocodée à la volée)."""
    exploitation = _exploitation(request)
    ville = VilleMeteo.objects.filter(exploitation=exploitation, slug=slug).first() if exploitation else None

    if ville:
        lat, lon, location = ville.latitude, ville.longitude, ville.nom
    else:
        try:
            geo = geocode(slug.replace("-", " "))
        except Exception:  # noqa: BLE001
            geo = None
        if geo:
            lat, lon, location = geo
        else:
            lat, lon, location = None, None, slug.replace("-", " ").title()

    weather, error = None, None
    if lat is not None:
        try:
            weather = fetch_weather(lat, lon)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    else:
        error = _("Lieu introuvable.")

    # Historique de cette ville : filtré par proximité de coordonnées (robuste aux libellés)
    if exploitation and lat is not None:
        history = list(ReleveMeteo.objects.filter(
            exploitation=exploitation,
            latitude__range=(lat - 0.05, lat + 0.05),
            longitude__range=(lon - 0.05, lon + 0.05),
        )[:60])
    else:
        history = []

    # Données pour les graphiques (ordre chronologique : ancien → récent)
    chrono = list(reversed(history))
    chart_data = {
        "labels": [r.captured_at.strftime("%d/%m %H:%M") for r in chrono],
        "temperature": [r.temperature for r in chrono],
        "humidite": [r.humidite for r in chrono],
        "vent": [r.vent for r in chrono],
        "pluie": [r.pluie for r in chrono],
    }

    return render(request, "meteo/meteo.html", {
        "weather": weather,
        "error": error,
        "location": location,
        # lat/lon en chaînes avec un point (évite la virgule de localisation FR dans les formulaires)
        "lat": f"{lat:.4f}" if lat is not None else "",
        "lon": f"{lon:.4f}" if lon is not None else "",
        "slug": slug,
        "ville": ville,
        "already_saved": ville is not None,
        "history": history[:30],
        "chart_data": chart_data,
        "frequences": VilleMeteo.Frequence.choices,
        "default_frequence": VilleMeteo.Frequence.QUOTIDIEN,
        "page_title": location,
    })


@login_required
@require_POST
def meteo_capturer(request):
    """Enregistre un relevé météo (snapshot). Renvoie du JSON en AJAX, sinon redirige."""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    exploitation = _exploitation(request, create=True)
    try:
        lat, lon = float(request.POST["lat"]), float(request.POST["lon"])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"ok": False}, status=400) if is_ajax else redirect("meteo:index")
    lieu = (request.POST.get("lieu") or "").strip()
    slug = request.POST.get("slug") or slugify(lieu) or "ville"

    rel, err = None, None
    if exploitation:
        try:
            w = fetch_weather(lat, lon)
            cur = w["current"]
            today = w["days"][0] if w["days"] else {}
            rel = ReleveMeteo.objects.create(
                exploitation=exploitation, lieu=lieu, latitude=lat, longitude=lon,
                temperature=cur.get("temp"), humidite=cur.get("humidite"),
                vent=cur.get("vent"), pluie=cur.get("pluie"),
                et0=today.get("et0"), libelle=cur.get("label", ""),
            )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)

    if is_ajax:
        if rel is None:
            return JsonResponse({"ok": False, "error": err or "indisponible"}, status=502)
        return JsonResponse({"ok": True, "releve": {
            "date": rel.captured_at.strftime("%d/%m/%Y %H:%M"),
            "label": rel.captured_at.strftime("%d/%m %H:%M"),
            "libelle": rel.libelle,
            "temperature": rel.temperature, "humidite": rel.humidite,
            "vent": rel.vent, "pluie": rel.pluie, "et0": rel.et0,
        }})

    messages.success(request, _("Relevé météo capturé.")) if rel else messages.error(
        request, _("Échec de la capture : %(e)s") % {"e": err})
    return redirect("meteo:detail", slug=slug)


@login_required
@require_POST
def ville_add(request):
    """Enregistre la ville courante dans les favoris, puis ouvre son détail."""
    try:
        lat, lon = float(request.POST["lat"]), float(request.POST["lon"])
    except (KeyError, ValueError, TypeError):
        return redirect("meteo:index")
    nom = (request.POST.get("nom") or "").strip()[:255] or "Ville"
    slug = slugify(nom) or "ville"
    exploitation = _exploitation(request, create=True)
    if exploitation:
        VilleMeteo.objects.get_or_create(
            exploitation=exploitation, slug=slug,
            defaults={"nom": nom, "latitude": lat, "longitude": lon},
        )
    return redirect("meteo:detail", slug=slug)


@login_required
@require_POST
def ville_delete(request, pk):
    exploitation = _exploitation(request)
    VilleMeteo.objects.filter(pk=pk, exploitation=exploitation).delete()
    return redirect("meteo:index")


@csrf_exempt
@require_POST
def cron_capturer(request):
    """Endpoint machine (token) déclenché par un CronJob : lance les captures dues."""
    token = getattr(settings, "CRON_TOKEN", "")
    provided = request.headers.get("X-Cron-Token") or request.GET.get("token")
    if not token or provided != token:
        return JsonResponse({"error": "unauthorized"}, status=403)
    captured = run_scheduled_captures(force=False)
    return JsonResponse({"ok": True, "captured": captured})
