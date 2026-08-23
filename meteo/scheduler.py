"""Logique de capture planifiée (par ville), partagée par la commande et l'endpoint cron."""

from django.utils import timezone

from .models import ReleveMeteo, VilleMeteo
from .services import fetch_weather


def run_scheduled_captures(force=False):
    """Capture la météo des villes dont la capture auto est activée et « due ».

    Renvoie le nombre de relevés enregistrés.
    """
    now = timezone.now()
    total = 0
    for v in VilleMeteo.objects.filter(capture_auto=True):
        if not (force or v.capture_due(now)):
            continue
        try:
            w = fetch_weather(v.latitude, v.longitude)
            cur = w["current"]
            today = w["days"][0] if w["days"] else {}
            ReleveMeteo.objects.create(
                exploitation=v.exploitation, lieu=v.nom,
                latitude=v.latitude, longitude=v.longitude,
                temperature=cur.get("temp"), humidite=cur.get("humidite"),
                vent=cur.get("vent"), pluie=cur.get("pluie"),
                et0=today.get("et0"), libelle=cur.get("label", ""),
            )
            total += 1
        except Exception:  # noqa: BLE001 — météo ville indisponible, on continue
            continue
        v.capture_last_run = now
        v.save(update_fields=["capture_last_run"])
    return total
