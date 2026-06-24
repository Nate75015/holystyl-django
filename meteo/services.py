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

# Codes WMO → (libellé FR, emoji)
_WMO = {
    0: ("Ciel dégagé", "☀️"),
    1: ("Plutôt dégagé", "🌤️"),
    2: ("Partiellement nuageux", "⛅"),
    3: ("Couvert", "☁️"),
    45: ("Brouillard", "🌫️"),
    48: ("Brouillard givrant", "🌫️"),
    51: ("Bruine légère", "🌦️"),
    53: ("Bruine", "🌦️"),
    55: ("Bruine dense", "🌧️"),
    56: ("Bruine verglaçante", "🌧️"),
    57: ("Bruine verglaçante", "🌧️"),
    61: ("Pluie faible", "🌦️"),
    63: ("Pluie", "🌧️"),
    65: ("Pluie forte", "🌧️"),
    66: ("Pluie verglaçante", "🌧️"),
    67: ("Pluie verglaçante", "🌧️"),
    71: ("Neige faible", "🌨️"),
    73: ("Neige", "❄️"),
    75: ("Neige forte", "❄️"),
    77: ("Grains de neige", "❄️"),
    80: ("Averses faibles", "🌦️"),
    81: ("Averses", "🌧️"),
    82: ("Averses violentes", "⛈️"),
    85: ("Averses de neige", "🌨️"),
    86: ("Averses de neige", "🌨️"),
    95: ("Orage", "⛈️"),
    96: ("Orage avec grêle", "⛈️"),
    99: ("Orage avec grêle", "⛈️"),
}


def _wmo(code):
    return _WMO.get(int(code) if code is not None else -1, ("—", "❓"))


def _r(value, default=None):
    """Arrondi sûr (None toléré)."""
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return default


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
    req = urllib.request.Request(url, headers={"User-Agent": "Holystyl/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    cur = data.get("current", {})
    clabel, cemoji = _wmo(cur.get("weather_code"))
    current = {
        "temp": _r(cur.get("temperature_2m")),
        "ressenti": _r(cur.get("apparent_temperature")),
        "humidite": _r(cur.get("relative_humidity_2m")),
        "pluie": cur.get("precipitation"),
        "vent": _r(cur.get("wind_speed_10m")),
        "label": clabel,
        "emoji": cemoji,
    }

    daily = data.get("daily", {})
    times = daily.get("time", [])
    days = []
    for i, d in enumerate(times):
        dt = date.fromisoformat(d)
        label, emoji = _wmo(daily.get("weather_code", [None] * len(times))[i])
        days.append({
            "date": dt,
            "jour": _JOURS[dt.weekday()],
            "label": label,
            "emoji": emoji,
            "tmax": _r(daily.get("temperature_2m_max", [None])[i]),
            "tmin": _r(daily.get("temperature_2m_min", [None])[i]),
            "pluie": daily.get("precipitation_sum", [None])[i],
            "proba_pluie": _r(daily.get("precipitation_probability_max", [None])[i]),
            "et0": daily.get("et0_fao_evapotranspiration", [None])[i],
            "vent": _r(daily.get("wind_speed_10m_max", [None])[i]),
        })

    return {"current": current, "days": days}
