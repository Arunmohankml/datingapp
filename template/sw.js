// Basic Service Worker for PWA
const CACHE_NAME = 'srm-match-cache-v1';
const urlsToCache = [];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // CRITICAL: Never intercept POST requests or API calls.
  // POST bodies are consumed after first read — re-fetching causes ERR_FAILED.
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) {
    return; // Let browser handle it natively
  }

  // CRITICAL: Let browser natively handle cross-origin requests (e.g. CDNs for AI models)
  if (url.origin !== location.origin) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached response or fetch from network
        return response || fetch(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
