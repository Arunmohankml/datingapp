// Service Worker for SRM Match PWA - v2 (Cache cleared)
const CACHE_NAME = 'srm-match-cache-v2';
const urlsToCache = [];

self.addEventListener('install', event => {
  // Take control immediately - don't wait for old SW to die
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // CRITICAL: Never intercept POST requests or API calls.
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) {
    return;
  }

  // CRITICAL: Let browser natively handle cross-origin requests (CDNs for AI models)
  if (url.origin !== location.origin) {
    return;
  }

  // Network first - don't serve cached redirects
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

self.addEventListener('activate', event => {
  // Delete ALL old caches immediately
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(cacheNames.map(name => caches.delete(name)))
    ).then(() => self.clients.claim()) // Take control of all open pages
  );
});
