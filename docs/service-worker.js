// FRLG タイプ相性チェッカー — Service Worker
//
// Strategy:
//   - Static shell (HTML / JS / CSS / icons / manifest) → cache-first.
//     These only change when we redeploy; a fresh build bumps CACHE_VERSION
//     (build_data.py rewrites the constant below) so the activate handler
//     drops the old cache and the install handler refills it.
//   - data.json → network-first, fall back to cached copy when offline.
//     This is the only file that changes between deploys without code
//     edits, and we want users to see updates immediately without having
//     to bump a version. The cached copy is refreshed every time a
//     network fetch succeeds, so offline mode stays current.

// Bumped automatically by build_data.py on every rebuild. Do not edit by
// hand unless you know what you're doing.
const CACHE_VERSION = 'frlg-2026-05-10T06-02-37Z';

const STATIC_ASSETS = [
  './',
  './index.html',
  './app.js',
  './style.css',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
];

const DATA_PATH = './data.json';

self.addEventListener('install', (event) => {
  event.waitUntil(
    // Pre-cache static + an initial data.json so the app works offline
    // immediately after install, even before the first network success.
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll([...STATIC_ASSETS, DATA_PATH]),
    ),
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

function isDataRequest(url) {
  return url.pathname.endsWith('/data.json');
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (isDataRequest(url)) {
    // Network-first for data.json so spec changes (new abilities, fixed
    // descriptions, etc.) ship the moment GitHub Pages serves them.
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then((cache) =>
              cache.put(event.request, copy),
            );
          }
          return res;
        })
        .catch(() => caches.match(event.request)),
    );
    return;
  }

  // Cache-first for everything else (the static app shell).
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) =>
            cache.put(event.request, copy),
          );
        }
        return res;
      });
    }),
  );
});
