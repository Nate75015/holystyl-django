// Enregistrement du service worker (PWA offline-first).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js', { scope: '/' }).catch(() => {});
  });
}
