const CACHE = 'knotspot-v1';
const STATIC_CACHE = 'knotspot-static-v1';
const IMAGE_CACHE = 'knotspot-images-v1';

const PRECACHE_URLS = [
  '/',
  '/login/',
  '/manifest.json',
  '/static/favicon.png',
];

// ── Install – precache app shell ──
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch(() => {});
    }).then(() => self.skipWaiting())
  );
});

// ── Activate – clean old caches ──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE && k !== STATIC_CACHE && k !== IMAGE_CACHE)
          .map((k) => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// ── Fetch strategies ──
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // skip non-GET
  if (request.method !== 'GET') return;

  // Chrome extension requests
  if (url.protocol === 'chrome-extension:') return;

  // Images – cache first
  if (request.destination === 'image') {
    event.respondWith(cacheFirst(request, IMAGE_CACHE));
    return;
  }

  // Static assets – cache first
  if (
    request.destination === 'script' ||
    request.destination === 'style' ||
    request.destination === 'font'
  ) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Navigation – network first with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // Everything else – network with cache fallback
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok && response.type === 'basic') {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('', { status: 408, statusText: 'Offline' });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match('/login/');
  }
}

// ── Notification click ──
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const c of clients) {
        if (c.url === url && 'focus' in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

// ── Firebase Cloud Messaging (background messages) ──
importScripts('https://www.gstatic.com/firebasejs/10.11.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.11.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyDNiJROEM1-oa2kidoUorjFPS4FvP_et0M",
  authDomain: "datingapp-636fa.firebaseapp.com",
  projectId: "datingapp-636fa",
  storageBucket: "datingapp-636fa.firebasestorage.app",
  messagingSenderId: "848138254029",
  appId: "1:848138254029:web:db606ec479cc1220805b84",
  measurementId: "G-VVG7199H45"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const { notification: data, data: extra } = payload;
  const title = data?.title || 'KnotSpot';
  const options = {
    body: data?.body || '',
    icon: '/static/favicon.png',
    badge: '/static/favicon.png',
    data: { url: extra?.url || '/' },
    vibrate: [200, 100, 200],
  };
  self.registration.showNotification(title, options);
});
