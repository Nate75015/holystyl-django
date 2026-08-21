"""Vues du socle : autocomplétion d'adresse et sonde de santé.

Les tableaux de bord ont migré vers l'app `dashboard` : ils agrègent du métier,
le socle n'a pas à en dépendre.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import adresse as adresse_service


@login_required
@require_GET
def adresse_suggestions(request):
    """Suggestions d'adresse pour les formulaires (Google Places ou BAN)."""
    resultats = adresse_service.suggest(request.GET.get("q", ""))
    return JsonResponse({"fournisseur": adresse_service.fournisseur(), "results": resultats})


@login_required
@require_GET
def adresse_details(request):
    """Composants d'une suggestion qui n'en portait pas (cas Google Places)."""
    return JsonResponse({"adresse": adresse_service.details(request.GET.get("id", ""))})


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
