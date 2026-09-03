// Service worker minimal (socle PWA).
// La stratégie offline complète (cache des écrans + file d'écritures) sera
// implémentée à la phase de finalisation (cf. MIGRATION_PLAN §10).
const CACHE = 'isidor-v1';
const PRECACHE = ['/static/css/app.css', '/static/js/app.js', '/static/icons/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  // Cache-first pour les assets statiques uniquement.
  if (request.url.includes('/static/')) {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
