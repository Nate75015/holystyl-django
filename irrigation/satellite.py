"""Acquisition Sentinel-2 via Copernicus Data Space Ecosystem (CDSE).

Calcule NDVI (vigueur du couvert) et NDWI (teneur en eau) sur le contour d'une
parcelle et enregistre un point par passage satellite clair de la fenêtre.

Configuration (.env) :
    COPERNICUS_CLIENT_ID=...
    COPERNICUS_CLIENT_SECRET=...

Portage du module éprouvé du DTI. Les cartes colorées (PNG) ne sont pas
reprises : l'affichage des parcelles n'en montre pas, et les enregistrer
demanderait un stockage média que cette application n'a pas ici.
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

# Déploiement Sentinel Hub. Par défaut Planet Insights (standalone) ; pour
# Copernicus Data Space, pointer SENTINELHUB_BASE et SENTINELHUB_TOKEN_URL
# vers *.dataspace.copernicus.eu.
SH_BASE = os.getenv("SENTINELHUB_BASE", "https://services.sentinel-hub.com").rstrip("/")
TOKEN_URL = os.getenv(
    "SENTINELHUB_TOKEN_URL",
    "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
)
STATISTICS_URL = f"{SH_BASE}/api/v1/statistics"

# Fenêtre de recherche (jours) et couverture nuageuse maximale tolérée (%).
LOOKBACK_DAYS = 45
MAX_CLOUD_PCT = 70

_CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

# Cache mémoire du jeton OAuth (local au process).
_token_cache = {"value": None, "expires_at": dt.datetime.min}


class SatelliteError(Exception):
    """Erreur fonctionnelle : configuration, réseau, contour ou absence d'image."""


# Deux sorties FLOAT32 (ndvi, ndwi) + masque de validité. La couche SCL exclut
# nuages, ombres de nuages, neige et pixels saturés.
_STATS_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B03", "B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndwi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(s) {
  var bad = (s.SCL == 3 || s.SCL == 8 || s.SCL == 9 || s.SCL == 10 || s.SCL == 11);
  var valid = (s.dataMask == 1 && !bad) ? 1 : 0;
  var ndvi = index(s.B08, s.B04);
  var ndwi = index(s.B03, s.B08);
  return { ndvi: [ndvi], ndwi: [ndwi], dataMask: [valid] };
}
"""


def _credentials():
    cid = os.getenv("COPERNICUS_CLIENT_ID", "").strip()
    secret = os.getenv("COPERNICUS_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        raise SatelliteError(
            "Identifiants Copernicus manquants : renseignez COPERNICUS_CLIENT_ID "
            "et COPERNICUS_CLIENT_SECRET dans le fichier .env."
        )
    return cid, secret


def is_configured():
    """Les identifiants Copernicus sont-ils présents ?"""
    return bool(os.getenv("COPERNICUS_CLIENT_ID", "").strip()
                and os.getenv("COPERNICUS_CLIENT_SECRET", "").strip())


def _get_token():
    now = dt.datetime.utcnow()
    if _token_cache["value"] and _token_cache["expires_at"] > now:
        return _token_cache["value"]
    cid, secret = _credentials()
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": secret,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SatelliteError(
            "Authentification Copernicus refusée (vérifiez vos identifiants)."
        ) from e
    except urllib.error.URLError as e:
        raise SatelliteError(f"Copernicus injoignable : {e.reason}") from e
    token = data.get("access_token")
    if not token:
        raise SatelliteError("Réponse d'authentification Copernicus invalide.")
    ttl = int(data.get("expires_in", 600))
    _token_cache["value"] = token
    _token_cache["expires_at"] = now + dt.timedelta(seconds=max(60, ttl - 60))
    return token


def _post(url, payload, token, timeout=45):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise SatelliteError(f"Erreur Copernicus ({e.code}) : {detail}") from e
    except urllib.error.URLError as e:
        raise SatelliteError(f"Copernicus injoignable : {e.reason}") from e


def _geometry(parcelle):
    geom = parcelle.boundaries
    if not geom or not isinstance(geom, dict) or "type" not in geom:
        raise SatelliteError(
            "Cette parcelle n'a pas de contour : importez-la depuis le cadastre "
            "(onglet Carte) pour permettre l'analyse satellite."
        )
    return geom


def _time_range(days=LOOKBACK_DAYS):
    today = dt.date.today()
    debut = today - dt.timedelta(days=days)
    return f"{debut.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z"


def _statistics(geom, token):
    t_from, t_to = _time_range()
    payload = {
        "input": {
            "bounds": {"geometry": geom, "properties": {"crs": _CRS84}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {"maxCloudCoverage": MAX_CLOUD_PCT},
            }],
        },
        "aggregation": {
            "timeRange": {"from": t_from, "to": t_to},
            "aggregationInterval": {"of": "P1D"},
            "resx": 10, "resy": 10,
            "evalscript": _STATS_EVALSCRIPT,
        },
    }
    return _post(STATISTICS_URL, payload, token)


def _serie_claire(stats):
    """Passages clairs de la fenêtre, du plus ancien au plus récent.

    Un passage sans pixel valide (entièrement nuageux) est écarté : c'est ce
    qui garantit que chaque point de la courbe correspond à une vraie mesure.
    """
    serie = []
    for item in stats.get("data", []):
        sorties = item.get("outputs", {})
        try:
            ndvi = sorties["ndvi"]["bands"]["B0"]["stats"]
            ndwi = sorties["ndwi"]["bands"]["B0"]["stats"]
        except (KeyError, TypeError):
            continue
        echantillons = ndvi.get("sampleCount", 0)
        sans_donnee = ndvi.get("noDataCount", 0)
        if echantillons - sans_donnee <= 0:
            continue
        jour = (item.get("interval", {}).get("from", "") or "")[:10]
        if not jour:
            continue
        nuages = round(100 * sans_donnee / echantillons, 1) if echantillons else None
        serie.append({"date": jour, "nuages": nuages, "ndvi": ndvi, "ndwi": ndwi})
    serie.sort(key=lambda point: point["date"])
    if not serie:
        raise SatelliteError(
            f"Aucune image claire sur les {LOOKBACK_DAYS} derniers jours "
            "(couverture nuageuse). Réessayez plus tard."
        )
    return serie


def analyser(parcelle):
    """Analyse une parcelle et enregistre un point par passage clair.

    Idempotent par (parcelle, date) : réanalyser complète l'historique au lieu
    de l'écraser. Renvoie la mesure la plus récente.
    """
    from .models import NdviData

    geom = _geometry(parcelle)
    token = _get_token()
    serie = _serie_claire(_statistics(geom, token))

    derniere = None
    for point in serie:
        jour = dt.date.fromisoformat(point["date"])
        horodatage = timezone.make_aware(dt.datetime.combine(jour, dt.time.min))
        ndvi, ndwi = point["ndvi"], point["ndwi"]
        derniere, _cree = NdviData.objects.update_or_create(
            parcelle=parcelle,
            acquisition_date=horodatage,
            defaults={
                "exploitation": parcelle.exploitation,
                "ndvi_mean": ndvi.get("mean"),
                "ndvi_min": ndvi.get("min"),
                "ndvi_max": ndvi.get("max"),
                "ndvi_std": ndvi.get("stDev"),
                "ndwi_mean": ndwi.get("mean"),
                "ndwi_min": ndwi.get("min"),
                "ndwi_max": ndwi.get("max"),
                "cloud_coverage": point["nuages"],
                "source": "sentinel2",
            },
        )
    return derniere
