// FRLG タイプ相性チェッカー — Service Worker
//
// Strategy: pre-cache the entire static app on install. Serve everything
// cache-first since the assets only change on a deploy. Bump CACHE_VERSION
// to force clients to drop the old cache and re-fetch on next load.

const CACHE_VERSION = 'frlg-v1';

const ASSETS = [
  './',
  './index.html',
  './app.js',
  './style.css',
  './data.json',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  // Only handle same-origin GETs; let anything else pass through normally.
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        // Tuck successful responses into the cache so navigations to
        // pages we didn't pre-cache still work offline next time.
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, copy));
        }
        return res;
      });
    }),
  );
});
