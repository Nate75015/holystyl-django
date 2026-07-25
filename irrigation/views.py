"""Vues web irrigation : module Irrigation (onglets) et Bassinage."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from meteo.models import VilleMeteo
from meteo.services import fetch_weather
from notifications.models import NotificationRule
from parcelles.models import Parcelle

from .models import (
    BassinageEvent, DtiScore, IrrigationProgram, IrrigationSession, IrrigationZone, PumpingStation,
)
from .services import DEFAULT_KC, calculate_dti_score

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


# ── DTI — Diagnostic Technique d'Irrigation ─────────────────────────

_DTI_COLORS = {"A": "#16a34a", "B": "#65a30d", "C": "#f59e0b", "D": "#ef4444"}
_DTI_LABELS = {
    "A": _("Excellent"), "B": _("Bon"), "C": _("À optimiser"), "D": _("Critique"),
}


@login_required
def dti(request):
    """Diagnostic technique d'irrigation : dernier score, historique, calculateur."""
    exploitation = _exploitation(request)
    scores = (
        DtiScore.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else DtiScore.objects.none()
    )
    latest = scores.first()
    parcelles = Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
    history = [
        {
            "date": s.calculated_at.strftime("%d/%m/%Y %H:%M"),
            "score": s.score,
            "numeric": round(s.score_numeric),
            "kwh": s.kwh_per_m3,
            "uniformity": s.uniformity_coeff,
            "parcelle": s.parcelle.name if s.parcelle else "",
            "color": _DTI_COLORS.get(s.score, "#94a3b8"),
        }
        for s in scores[:20]
    ]
    return render(request, "irrigation/dti.html", {
        "latest": latest,
        "latest_label": _DTI_LABELS.get(latest.score, "") if latest else "",
        "latest_color": _DTI_COLORS.get(latest.score, "#94a3b8") if latest else "#94a3b8",
        "history": history,
        "count": scores.count(),
        "parcelles": parcelles,
        "page_title": _("DTI"),
    })


@login_required
@require_POST
def dti_calculate(request):
    """Calcule et persiste un score DTI depuis le formulaire."""
    exploitation = _exploitation(request)
    kwh = _num(request.POST.get("kwh_per_m3"))
    if exploitation and kwh is not None:
        uniformity = _num(request.POST.get("uniformity"))
        uniformity = 90.0 if uniformity is None else uniformity
        result = calculate_dti_score(kwh, uniformity)
        DtiScore.objects.create(
            exploitation=exploitation,
            parcelle=Parcelle.objects.filter(pk=request.POST.get("parcelle") or None, exploitation=exploitation).first(),
            score=result.score,
            score_numeric=result.numeric,
            kwh_per_m3=kwh,
            flow_rate_m3h=_num(request.POST.get("flow_rate_m3h")),
            pressure_bar=_num(request.POST.get("pressure_bar")),
            uniformity_coeff=uniformity,
            recommendations=result.recommendations,
        )
        messages.success(request, _("Diagnostic DTI enregistré."))
    return redirect("irrigation:dti")


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
        BassinageEvent.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation else BassinageEvent.objects.none()
    )
    agg = events.aggregate(eau=Sum("water_used_m3"), duree=Avg("duration_minutes"))
    villes = list(VilleMeteo.objects.filter(exploitation=exploitation)) if exploitation else []
    return render(request, "irrigation/bassinage.html", {
        "events": events,
        "kpi_total": events.count(),
        "kpi_eau": round(agg["eau"] or 0, 1),
        "kpi_duree": round(agg["duree"]) if agg["duree"] else 0,
        "parcelles": Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none(),
        "villes": villes,
        "ville": villes[0] if villes else None,
        "bassinage_rules": _bassinage_rules(request.user),
        "statuses": BassinageEvent.Status.choices,
        "page_title": _("Bassinage"),
    })


@login_required
@require_POST
def bassinage_edit(request, pk):
    """Modifie un enregistrement de bassinage."""
    exploitation = _exploitation(request)
    event = get_object_or_404(BassinageEvent, pk=pk, exploitation=exploitation)
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if parcelle:
        event.parcelle = parcelle
    event.trigger_temperature = _num(request.POST.get("trigger_temperature"))
    dur = _int(request.POST.get("duration_minutes"), 0)
    if dur:
        event.duration_minutes = max(1, dur)
    event.water_used_m3 = _num(request.POST.get("water_used_m3"))
    status = request.POST.get("status")
    if status in BassinageEvent.Status.values:
        event.status = status
    event.notes = (request.POST.get("notes") or "").strip()
    event.save()
    messages.success(request, _("Bassinage mis à jour."))
    return redirect("irrigation:bassinage")


@login_required
@require_POST
def bassinage_toggle(request, pk):
    """Bascule le statut d'un bassinage : Actif ↔ Inactif (terminé)."""
    exploitation = _exploitation(request)
    event = get_object_or_404(BassinageEvent, pk=pk, exploitation=exploitation)
    if event.status == BassinageEvent.Status.ACTIVE:
        event.status = BassinageEvent.Status.COMPLETED
        if not event.end_time:
            event.end_time = timezone.now()
    else:
        event.status = BassinageEvent.Status.ACTIVE
        event.end_time = None
    event.save(update_fields=["status", "end_time"])
    return redirect("irrigation:bassinage")


@login_required
@require_POST
def bassinage_delete(request, pk):
    """Supprime un enregistrement de bassinage."""
    exploitation = _exploitation(request)
    get_object_or_404(BassinageEvent, pk=pk, exploitation=exploitation).delete()
    messages.success(request, _("Bassinage supprimé."))
    return redirect("irrigation:bassinage")


def _bassinage_rules(user):
    """Alertes bassinage = règles de notification « météo · température · seuil dépassé »."""
    return (
        NotificationRule.objects.filter(
            user=user,
            type=NotificationRule.Type.METEO,
            metric=NotificationRule.Metric.TEMPERATURE,
            condition_type=NotificationRule.ConditionType.SEUIL_DEPASSE,
        )
        .select_related("ville")
        .order_by("ville__nom", "-threshold")
    )


@login_required
@require_POST
def bassinage_settings(request):
    """Ajoute une alerte bassinage : une règle de notification « T° ≥ seuil » pour une ville."""
    exploitation = _exploitation(request)
    ville = (
        VilleMeteo.objects.filter(exploitation=exploitation, slug=request.POST.get("ville")).first()
        if exploitation else None
    )
    seuil = _num(request.POST.get("seuil_bassinage_c"))
    if ville and seuil is not None:
        NotificationRule.objects.create(
            user=request.user,
            name=_("Bassinage — %(v)s ≥ %(s)s°C") % {"v": ville.nom, "s": f"{seuil:g}"},
            type=NotificationRule.Type.METEO,
            metric=NotificationRule.Metric.TEMPERATURE,
            condition_type=NotificationRule.ConditionType.SEUIL_DEPASSE,
            threshold=seuil,
            ville=ville,
            enabled=True,
        )
        messages.success(request, _("Alerte bassinage ajoutée pour %(v)s.") % {"v": ville.nom})
    else:
        messages.error(request, _("Choisissez une ville et un seuil pour ajouter l'alerte."))
    return redirect("irrigation:bassinage")


@login_required
@require_POST
def bassinage_create(request):
    """Déclenche un bassinage manuel (crée un BassinageEvent actif)."""
    exploitation = _exploitation(request)
    parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
    if exploitation and parcelle:
        BassinageEvent.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            start_time=timezone.now(),
            duration_minutes=max(1, _int(request.POST.get("duration_minutes"), 20)),
            trigger_temperature=_num(request.POST.get("trigger_temperature")),
            triggered_by=BassinageEvent.TriggeredBy.MANUAL,
            status=BassinageEvent.Status.ACTIVE,
        )
        messages.success(request, _("Bassinage déclenché."))
    return redirect("irrigation:bassinage")


# Seuils de gel critiques par culture/stade (référence agronomique).
_CULTURES_SEUILS = [
    (_("Vigne (débourrement)"), "-1.5°C"),
    (_("Vigne (floraison)"), "-0.5°C"),
    (_("Tomate (jeune plant)"), "+2°C"),
    (_("Blé (tallage)"), "-15°C"),
    (_("Maïs (levée)"), "0°C"),
    (_("Abricotier (fleurs)"), "-0.5°C"),
]


# Description du niveau de risque (tooltip).
_RISK_DESC = {
    "aucun": _("Aucun risque de gel (min ≥ 3°C)"),
    "faible": _("Risque faible (0 à 3°C)"),
    "modere": _("Risque modéré (-1 à 0°C)"),
    "eleve": _("Risque élevé (-3 à -1°C)"),
    "critique": _("Risque critique (min < -3°C)"),
    "inconnu": _("Données indisponibles"),
}


# Niveau de risque de gel selon la température minimale prévue (°C).
def _frost_risk(tmin):
    if tmin is None:
        return ("inconnu", _("Inconnu"), "#94a3b8")
    if tmin >= 3:
        return ("aucun", _("Aucun"), "#10b981")
    if tmin >= 0:
        return ("faible", _("Faible"), "#3b82f6")
    if tmin >= -1:
        return ("modere", _("Modéré"), "#f59e0b")
    if tmin >= -3:
        return ("eleve", _("Élevé"), "#f97316")
    return ("critique", _("Critique"), "#ef4444")


def _forecast_days(lat, lon):
    """Prévisions 7 jours pour des coordonnées (cache 30 min), ou [] si indisponible."""
    if lat is None or lon is None:
        return []
    lat, lon = round(lat, 3), round(lon, 3)
    cache_key = f"antigel_days:{lat}:{lon}"
    days = cache.get(cache_key)
    if days is None:
        try:
            days = fetch_weather(lat, lon).get("days") or []
        except Exception:  # noqa: BLE001 — météo indisponible
            return []
        cache.set(cache_key, days, 1800)
    return days


@login_required
def antigel(request):
    exploitation = _exploitation(request)
    # Lieu : parmi les villes enregistrées sur /meteo/ (défaut = 1re), sinon l'exploitation.
    villes = list(VilleMeteo.objects.filter(exploitation=exploitation)) if exploitation else []
    ville = next((v for v in villes if v.slug == request.GET.get("ville")), villes[0] if villes else None)
    if ville:
        lat, lon = ville.latitude, ville.longitude
    elif exploitation:
        lat, lon = exploitation.latitude, exploitation.longitude
    else:
        lat, lon = None, None

    forecast = []
    for d in _forecast_days(lat, lon):
        risk, label, color = _frost_risk(d.get("tmin"))
        forecast.append({
            "date": d.get("date"), "tmin": d.get("tmin"), "tmax": d.get("tmax"),
            "icon": d.get("icon"), "meteo": d.get("label"), "vent": d.get("vent"),
            "risk": risk, "risk_label": label, "color": color, "risk_desc": _RISK_DESC.get(risk, ""),
        })

    # Alerte : nuits à risque (Élevé / Critique) dans les 5 prochains jours.
    window = forecast[:5]
    at_risk = [f for f in window if f["risk"] in ("eleve", "critique")]
    mins = [f["tmin"] for f in window if f["tmin"] is not None]
    alert = {"nb": len(at_risk), "tmin": min(mins) if mins else None} if at_risk else None

    return render(request, "irrigation/antigel.html", {
        "forecast": forecast,
        "alert": alert,
        "cultures": _CULTURES_SEUILS,
        "villes": villes,
        "ville": ville,
        "gel_rules": _gel_rules(request.user),
        "seuil": exploitation.seuil_alerte_gel_c if exploitation else 2.0,
        "page_title": _("Anti-gel"),
    })


def _gel_rules(user):
    """Alertes anti-gel = règles de notification « météo · température · seuil non atteint »."""
    return (
        NotificationRule.objects.filter(
            user=user,
            type=NotificationRule.Type.METEO,
            metric=NotificationRule.Metric.TEMPERATURE,
            condition_type=NotificationRule.ConditionType.SEUIL_SOUS,
        )
        .select_related("ville")
        .order_by("ville__nom", "threshold")
    )


@login_required
@require_POST
def antigel_settings(request):
    """Ajoute une alerte anti-gel : une règle de notification « T° min ≤ seuil » pour une ville."""
    exploitation = _exploitation(request)
    ville = (
        VilleMeteo.objects.filter(exploitation=exploitation, slug=request.POST.get("ville")).first()
        if exploitation else None
    )
    seuil = _num(request.POST.get("seuil_alerte_gel_c"))
    if ville and seuil is not None:
        signe = f"+{seuil:g}" if seuil > 0 else f"{seuil:g}"
        NotificationRule.objects.create(
            user=request.user,
            name=_("Gel — %(v)s ≤ %(s)s°C") % {"v": ville.nom, "s": signe},
            type=NotificationRule.Type.METEO,
            metric=NotificationRule.Metric.TEMPERATURE,
            condition_type=NotificationRule.ConditionType.SEUIL_SOUS,
            threshold=seuil,
            ville=ville,
            enabled=True,
        )
        messages.success(request, _("Alerte anti-gel ajoutée pour %(v)s.") % {"v": ville.nom})
    else:
        messages.error(request, _("Choisissez une ville et un seuil pour ajouter l'alerte."))
    return redirect("irrigation:antigel")
