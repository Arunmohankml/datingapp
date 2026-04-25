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
  // Let the browser handle all network requests natively.
  // We keep this event listener active because Chrome requires a fetch handler 
  // to recognize the app as an installable PWA and trigger the install banner.
});

self.addEventListener('activate', event => {
  // Delete ALL old caches immediately
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(cacheNames.map(name => caches.delete(name)))
    ).then(() => self.clients.claim()) // Take control of all open pages
  );
});
