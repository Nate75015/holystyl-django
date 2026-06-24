"""Vue web Météo : conditions courantes + prévisions 7 jours (Open-Meteo)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .services import fetch_weather

# Position par défaut si l'exploitation n'a pas de coordonnées (Avignon).
_DEFAULT_LAT, _DEFAULT_LON = 43.95, 4.81


@login_required
def meteo(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    lat = exploitation.latitude if exploitation else None
    lon = exploitation.longitude if exploitation else None
    location = exploitation.city or exploitation.name if exploitation else ""

    # Repli : 1ʳᵉ parcelle géolocalisée, sinon position par défaut
    if lat is None or lon is None:
        parcelle = (
            Parcelle.objects.filter(exploitation=exploitation, latitude__isnull=False).first()
            if exploitation else None
        )
        if parcelle:
            lat, lon, location = parcelle.latitude, parcelle.longitude, parcelle.commune or parcelle.name
        else:
            lat, lon = _DEFAULT_LAT, _DEFAULT_LON
            location = location or "Avignon"

    weather, error = None, None
    try:
        weather = fetch_weather(lat, lon)
    except Exception as exc:  # noqa: BLE001 — erreur réseau/API affichée à l'utilisateur
        error = str(exc)

    return render(request, "meteo/meteo.html", {
        "weather": weather,
        "error": error,
        "location": location or _("Votre exploitation"),
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "page_title": _("Météo"),
    })
