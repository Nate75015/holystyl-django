"""Vues du socle : dashboard (Pulse) et endpoint de santé."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from exploitations.models import Exploitation
from exploitations.services import compute_kpis


def _reversed(qs):
    return list(reversed(list(qs)))


def _meteo_villes(exploitation, limit=2):
    """Les `limit` premières villes météo enregistrées, avec leur météo courante (cache 30 min)."""
    from django.core.cache import cache

    from meteo.models import VilleMeteo
    from meteo.services import fetch_current

    villes = list(VilleMeteo.objects.filter(exploitation=exploitation)[:limit])
    for v in villes:
        key = f"dash_current:{round(v.latitude, 3)}:{round(v.longitude, 3)}"
        cw = cache.get(key)
        if cw is None:
            try:
                cw = fetch_current(v.latitude, v.longitude)
            except Exception:  # noqa: BLE001 — météo ville indisponible
                cw = {"temp": None, "icon": "help_outline", "label": ""}
            cache.set(key, cw, 1800)
        v.temp, v.icon, v.label = cw.get("temp"), cw.get("icon"), cw.get("label")
    return villes


@login_required
def dashboard(request):
    """Écran Pulse : jauge DTI, météo, alertes et graphiques de l'exploitation."""
    from equipe.models import TeamMember
    from iot.models import IotAlert
    from irrigation.models import DtiScore, WaterMeter

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    kpis = compute_kpis(exploitation)

    dti = None
    dti_chart = None
    water_chart = None
    alerts = []
    meteo_villes = []
    etp_count = 0

    if exploitation is not None:
        meteo_villes = _meteo_villes(exploitation)
        etp_count = TeamMember.objects.filter(exploitation=exploitation).count()
        dti = DtiScore.objects.filter(exploitation=exploitation).first()

        history = _reversed(DtiScore.objects.filter(exploitation=exploitation)[:14])
        if history:
            dti_chart = {
                "labels": [d.calculated_at.strftime("%d/%m") for d in history],
                "data": [round(d.score_numeric, 1) for d in history],
                "color": "#0891b2",
                "label": "Score DTI",
            }

        meters = _reversed(WaterMeter.objects.filter(exploitation=exploitation)[:14])
        if meters:
            water_chart = {
                "labels": [m.reading_date.strftime("%d/%m") for m in meters],
                "data": [round(m.volume_m3, 1) for m in meters],
                "color": "#22c55e",
                "label": "Volume eau (m³)",
            }

        alerts = IotAlert.objects.filter(exploitation=exploitation, acknowledged=False)[:5]

    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Tableau de bord",
            "exploitation": exploitation,
            "needs_onboarding": exploitation is None,
            "kpis": kpis,
            "dti": dti,
            "dti_chart": dti_chart,
            "water_chart": water_chart,
            "alerts": alerts,
            "meteo_villes": meteo_villes,
            "etp_count": etp_count,
        },
    )


def healthz(request):
    """Sonde de disponibilité."""
    return JsonResponse({"app": "holystyl-django", "status": "ok"})


# Service worker servi à la RACINE (scope "/") — requis pour l'installabilité PWA.
_SW_JS = """
const CACHE = 'holystyl-v2';
self.addEventListener('install', () => { self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
// Network-first pour les assets statiques : toujours frais en ligne,
// cache seulement en secours hors-ligne (évite de servir un vieux CSS).
self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET' || !request.url.includes('/static/')) return;
  e.respondWith(
    fetch(request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match(request))
  );
});
""".strip()


def service_worker(request):
    """Sert le service worker depuis la racine avec le bon scope."""
    from django.http import HttpResponse

    resp = HttpResponse(_SW_JS, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp
