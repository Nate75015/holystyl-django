"""Vues web irrigation : module Irrigation (onglets) et Bassinage."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from meteo.services import fetch_weather
from parcelles.models import Parcelle

from .models import BassinageEvent, IrrigationProgram, IrrigationSession, IrrigationZone, PumpingStation
from .services import DEFAULT_KC

#: Tarif énergie moyen (€/kWh) pour estimer le coût quand la station n'en fournit pas.
_DEFAULT_ENERGY_TARIFF = 0.15


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _etc_defaults(exploitation, surface_ha):
    """Valeurs initiales du calculateur ETc (interactif côté client).

    ETP et pluie sont pré-remplis avec la météo du jour quand elle est disponible
    (ET0 FAO-56), mise en cache 30 min pour ne pas bloquer le chargement ; sinon
    des valeurs d'exemple modifiables. Kc par défaut = 0,85.
    """
    etp, pluie = None, None
    if exploitation and exploitation.latitude and exploitation.longitude:
        lat, lon = round(exploitation.latitude, 3), round(exploitation.longitude, 3)
        cache_key = f"irrig_et0:{lat}:{lon}"
        today = cache.get(cache_key)
        if today is None:
            try:
                weather = fetch_weather(lat, lon)
                day = (weather.get("days") or [{}])[0]
                today = {"et0": day.get("et0"), "pluie": day.get("pluie")}
                cache.set(cache_key, today, 1800)
            except Exception:  # noqa: BLE001 — météo indisponible → valeurs d'exemple
                today = {}
        etp, pluie = today.get("et0"), today.get("pluie")
    return {
        "etp": round(etp, 2) if etp is not None else 5.0,
        "kc": DEFAULT_KC,
        "pluie": round(pluie, 2) if pluie is not None else 0,
        "surface": round(surface_ha or 0, 2),
    }


@login_required
def irrigation(request):
    exploitation = _exploitation(request)
    zones = IrrigationZone.objects.filter(exploitation=exploitation).prefetch_related("parcelles") if exploitation else IrrigationZone.objects.none()
    programs = IrrigationProgram.objects.filter(exploitation=exploitation).prefetch_related("parcelles") if exploitation else IrrigationProgram.objects.none()
    sessions_qs = IrrigationSession.objects.filter(exploitation=exploitation) if exploitation else IrrigationSession.objects.none()
    stations = PumpingStation.objects.filter(exploitation=exploitation) if exploitation else PumpingStation.objects.none()
    sessions = list(sessions_qs[:20])

    # KPIs
    agg = sessions_qs.aggregate(eau=Sum("volume_delivered_m3"), energie=Sum("energy_kwh"))
    surface_ha = zones.aggregate(s=Sum("surface_ha"))["s"] or 0

    sessions_chart = None
    chrono = list(reversed(sessions))
    if any(s.volume_delivered_m3 for s in chrono):
        sessions_chart = {
            "labels": [s.start_time.strftime("%d/%m") for s in chrono],
            "data": [round(s.volume_delivered_m3 or 0, 1) for s in chrono],
            "color": "#0891b2",
            "label": "Volume (m³)",
        }

    ctx = {
        "page_title": _("Irrigation"),
        "tabs": [
            ("overview", _("Vue d'ensemble"), "insights"),
            ("zones", _("Zones"), "layers"),
            ("programs", _("Programmes"), "timer"),
            ("sessions", _("Sessions"), "waves"),
            ("calculators", _("Calculateurs"), "bar_chart"),
            ("stations", _("Stations"), "power_settings_new"),
        ],
        "kpis": [
            ("layers", zones.count(), "", _("Zones configurées")),
            ("play_arrow", sessions_qs.filter(end_time__isnull=True).count(), "", _("Sessions actives")),
            ("water_drop", round(agg["eau"] or 0), "m³", _("Eau totale")),
            ("check_circle", sessions_qs.count(), "", _("Sessions totales")),
            ("trending_up", round((agg["energie"] or 0) * _DEFAULT_ENERGY_TARIFF), "€", _("Coût total")),
        ],
        "zones": zones,
        "programs": programs,
        "sessions": sessions,
        "stations": stations,
        "sessions_chart": sessions_chart,
        "etc_init": _etc_defaults(exploitation, surface_ha),
        # Calculateurs interactifs : valeurs d'exemple modifiables côté client.
        "pluvio_init": {"debit": 4, "rangs": 5, "emetteurs": 1, "objectif": 4},
        "pumping_init": {"puissance": 7.5, "duree": 3, "efficacite": 0.75,
                         "tarif_energie": 0.15, "debit": 15, "tarif_eau": 0.5, "vfd": False},
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "irrigation_types": IrrigationZone.IrrigationType.choices,
        "frequencies": IrrigationProgram.Frequency.choices,
    }
    return render(request, "irrigation/irrigation.html", ctx)


def _num(value):
    """Nombre saisi (« 3,5 » ou « 3.5 ») → float, ou None si vide/invalide."""
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _int(value, default=None):
    """Entier saisi → int, ou `default` si vide/invalide."""
    try:
        return int(float(str(value).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return default


@login_required
@require_POST
def zone_create(request):
    """Crée une zone d'irrigation (soumise depuis la modale de /irrigation/).

    Une zone peut couvrir plusieurs parcelles : au moins une est requise.
    """
    exploitation = _exploitation(request)
    parcelles = (
        Parcelle.objects.filter(pk__in=request.POST.getlist("parcelles"), exploitation=exploitation)
        if exploitation
        else Parcelle.objects.none()
    )
    name = (request.POST.get("name") or "").strip()
    if exploitation and parcelles and name:
        itype = request.POST.get("irrigation_type")
        if itype not in IrrigationZone.IrrigationType.values:
            itype = IrrigationZone.IrrigationType.GOUTTE
        zone = IrrigationZone.objects.create(
            exploitation=exploitation,
            name=name,
            irrigation_type=itype,
            flow_rate_m3h=_num(request.POST.get("flow_rate_m3h")),
            surface_ha=_num(request.POST.get("surface_ha")),
            service_pressure_bar=_num(request.POST.get("service_pressure_bar")),
        )
        zone.parcelles.set(parcelles)
        messages.success(request, _("Zone « %(z)s » ajoutée.") % {"z": name})
    return redirect("irrigation:irrigation")


@login_required
@require_POST
def program_create(request):
    """Crée un programme d'irrigation (soumis depuis la modale de /irrigation/).

    Un programme peut piloter plusieurs parcelles : au moins une est requise.
    """
    exploitation = _exploitation(request)
    parcelles = (
        Parcelle.objects.filter(pk__in=request.POST.getlist("parcelles"), exploitation=exploitation)
        if exploitation
        else Parcelle.objects.none()
    )
    name = (request.POST.get("name") or "").strip()
    start_hour = _int(request.POST.get("start_hour"))
    duration = _int(request.POST.get("duration_minutes"))
    if exploitation and parcelles and name and start_hour is not None and duration is not None:
        freq = request.POST.get("frequency")
        if freq not in IrrigationProgram.Frequency.values:
            freq = IrrigationProgram.Frequency.DAILY
        program = IrrigationProgram.objects.create(
            exploitation=exploitation,
            name=name,
            start_hour=max(0, min(23, start_hour)),
            start_minute=max(0, min(59, _int(request.POST.get("start_minute"), 0))),
            duration_minutes=max(1, duration),
            frequency=freq,
            priority=max(1, min(10, _int(request.POST.get("priority"), 5))),
        )
        program.parcelles.set(parcelles)
        messages.success(request, _("Programme « %(p)s » ajouté.") % {"p": name})
    return redirect("irrigation:irrigation")


@login_required
@require_POST
def station_create(request):
    """Crée une station de pompage (soumise depuis la modale de /irrigation/)."""
    exploitation = _exploitation(request)
    name = (request.POST.get("name") or "").strip()
    if exploitation and name:
        efficiency = _num(request.POST.get("efficiency"))
        energy = _num(request.POST.get("energy_tariff_kwh"))
        water = _num(request.POST.get("water_tariff_m3"))
        PumpingStation.objects.create(
            exploitation=exploitation,
            name=name,
            max_flow_m3h=_num(request.POST.get("max_flow_m3h")),
            max_pressure_bar=_num(request.POST.get("max_pressure_bar")),
            power_kw=_num(request.POST.get("power_kw")),
            efficiency=efficiency if efficiency is not None else 0.75,
            energy_tariff_kwh=energy if energy is not None else 0.15,
            water_tariff_m3=water if water is not None else 0,
            has_variable_drive=bool(request.POST.get("has_variable_drive")),
        )
        messages.success(request, _("Station « %(s)s » ajoutée.") % {"s": name})
    return redirect("irrigation:irrigation")


@login_required
def bassinage(request):
    exploitation = _exploitation(request)
    events = (
        BassinageEvent.objects.filter(exploitation=exploitation) if exploitation else BassinageEvent.objects.none()
    )
    return render(request, "irrigation/bassinage.html", {"events": events, "page_title": _("Bassinage anti-gel")})
