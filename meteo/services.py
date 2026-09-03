"""Service météo via Open-Meteo (gratuit, sans clé API).

Renvoie la météo courante + prévisions 7 jours, avec des données agronomiques
utiles : pluie cumulée, évapotranspiration de référence (ET0 FAO-56), vent.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

_JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

# Codes WMO → (libellé FR, icône Material Icons Round monochrome)
_WMO = {
    0: ("Ciel dégagé", "wb_sunny"),
    1: ("Plutôt dégagé", "wb_sunny"),
    2: ("Partiellement nuageux", "wb_cloudy"),
    3: ("Couvert", "cloud"),
    45: ("Brouillard", "blur_on"),
    48: ("Brouillard givrant", "blur_on"),
    51: ("Bruine légère", "grain"),
    53: ("Bruine", "grain"),
    55: ("Bruine dense", "grain"),
    56: ("Bruine verglaçante", "grain"),
    57: ("Bruine verglaçante", "grain"),
    61: ("Pluie faible", "grain"),
    63: ("Pluie", "grain"),
    65: ("Pluie forte", "grain"),
    66: ("Pluie verglaçante", "grain"),
    67: ("Pluie verglaçante", "grain"),
    71: ("Neige faible", "ac_unit"),
    73: ("Neige", "ac_unit"),
    75: ("Neige forte", "ac_unit"),
    77: ("Grains de neige", "ac_unit"),
    80: ("Averses faibles", "grain"),
    81: ("Averses", "grain"),
    82: ("Averses violentes", "flash_on"),
    85: ("Averses de neige", "ac_unit"),
    86: ("Averses de neige", "ac_unit"),
    95: ("Orage", "flash_on"),
    96: ("Orage avec grêle", "flash_on"),
    99: ("Orage avec grêle", "flash_on"),
}


def _wmo(code):
    """(libellé, icône Material) pour un code WMO."""
    return _WMO.get(int(code) if code is not None else -1, ("—", "help_outline"))


def _r(value, default=None):
    """Arrondi sûr (None toléré)."""
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return default


def geocode(query):
    """Géocode un nom de lieu via l'API BAN → (lat, lon, libellé) ou None.

    Priorité aux communes (type=municipality) pour qu'« Avignon » renvoie la
    ville et non une localité/adresse homonyme ; repli sur une recherche large.
    """
    if not query:
        return None
    base = "https://api-adresse.data.gouv.fr/search/?limit=1&q=" + urllib.parse.quote(query)
    for url in (base + "&type=municipality", base):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Isidor/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                feats = (json.loads(resp.read()).get("features") or [])
        except Exception:  # noqa: BLE001 — on tente le repli
            feats = []
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            label = (feats[0].get("properties") or {}).get("label") or query
            return lat, lon, label
    return None


def fetch_current(lat, lon):
    """Météo courante allégée (température + conditions) — pour les chips de villes."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "timezone": "auto",
    }
    url = OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Isidor/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    cur = data.get("current", {})
    label, icon = _wmo(cur.get("weather_code"))
    return {"temp": _r(cur.get("temperature_2m")), "label": label, "icon": icon}


def fetch_weather(lat, lon):
    """Météo courante + prévisions 7 jours pour des coordonnées données."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,et0_fao_evapotranspiration,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": 7,
        "wind_speed_unit": "kmh",
    }
    url = OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Isidor/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    cur = data.get("current", {})
    clabel, cicon = _wmo(cur.get("weather_code"))
    current = {
        "temp": _r(cur.get("temperature_2m")),
        "ressenti": _r(cur.get("apparent_temperature")),
        "humidite": _r(cur.get("relative_humidity_2m")),
        "pluie": cur.get("precipitation"),
        "vent": _r(cur.get("wind_speed_10m")),
        "label": clabel,
        "icon": cicon,
    }

    daily = data.get("daily", {})
    times = daily.get("time", [])
    days = []
    for i, d in enumerate(times):
        dt = date.fromisoformat(d)
        label, icon = _wmo(daily.get("weather_code", [None] * len(times))[i])
        days.append({
            "date": dt,
            "jour": _JOURS[dt.weekday()],
            "label": label,
            "icon": icon,
            "tmax": _r(daily.get("temperature_2m_max", [None])[i]),
            "tmin": _r(daily.get("temperature_2m_min", [None])[i]),
            "pluie": daily.get("precipitation_sum", [None])[i],
            "proba_pluie": _r(daily.get("precipitation_probability_max", [None])[i]),
            "et0": daily.get("et0_fao_evapotranspiration", [None])[i],
            "vent": _r(daily.get("wind_speed_10m_max", [None])[i]),
        })

    return {"current": current, "days": days}


def villes_avec_meteo(exploitation, limite=2):
    """Les `limite` premières villes de l'exploitation, météo courante attachée.

    Cache de 30 min par coordonnées arrondies : plusieurs exploitations proches
    partagent le même appel. Une ville dont la météo est indisponible est
    renvoyée quand même, avec des valeurs neutres — un tableau de bord ne doit
    pas tomber parce qu'une API tierce est muette.
    """
    if exploitation is None:
        return []

    from django.core.cache import cache

    from .models import VilleMeteo

    villes = list(VilleMeteo.objects.filter(exploitation=exploitation)[:limite])
    for v in villes:
        cle = f"dash_current:{round(v.latitude, 3)}:{round(v.longitude, 3)}"
        courant = cache.get(cle)
        if courant is None:
            try:
                courant = fetch_current(v.latitude, v.longitude)
            except Exception:  # noqa: BLE001 — météo ville indisponible
                courant = {"temp": None, "icon": "help_outline", "label": ""}
            cache.set(cle, courant, 1800)
        v.temp, v.icon, v.label = courant.get("temp"), courant.get("icon"), courant.get("label")
    return villes
