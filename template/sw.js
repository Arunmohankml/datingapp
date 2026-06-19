const CACHE_NAME = 'srm-match-v2.0'; // v2: cleaned icons, removed root-level icon paths
const STATIC_ASSETS = [
  '/manifest.json',
  '/static/favicon.png'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_NAME) {
                        return caches.delete(name);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener("fetch", function(event) {
    // Only handle GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);

    // API and Chat routes bypass cache entirely
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/chat/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // HTML Pages (Navigation) -> Network First
    if (event.request.mode === 'navigate' || event.request.headers.get('accept').includes('text/html')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match(event.request);
            })
        );
        return;
    }

    // Static Assets -> Cache First, fallback to Network
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            
            return fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200) {
                    if (url.pathname.includes('/static/') || url.pathname.match(/\.(png|jpg|jpeg|svg|gif|woff2?|css|js)$/)) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseToCache));
                    }
                }
                return networkResponse;
            });
        })
    );
});

self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push Received.', event.data ? event.data.text() : 'No data');
    
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            console.error('Push data is not JSON:', e);
            data = { title: 'New Message', body: event.data.text() };
        }
    }

    // FCM sends notification data inside a 'notification' object or 'data' object
    const title = data.title || (data.notification ? data.notification.title : 'SRM Match');
    const body = data.body || (data.notification ? data.notification.body : 'You have a new message');
    const url = data.url || (data.data ? data.data.url : '/');

    const options = {
        body: body,
        icon: '/static/favicon.png',
        badge: '/static/favicon.png',
        vibrate: [100, 50, 100],
        data: { url: url }
    };

    // Show system notification unless the app is open and the user is already on the exact target URL
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            let isCurrentPage = false;
            for (var i = 0; i < windowClients.length; i++) {
                var client = windowClients[i];
                if (client.visibilityState === 'visible') {
                    try {
                        const clientUrl = new URL(client.url);
                        const targetUrl = new URL(url, client.url);
                        if (clientUrl.pathname === targetUrl.pathname) {
                            isCurrentPage = true;
                            break;
                        }
                    } catch (e) {
                        if (url !== '/' && client.url.includes(url)) {
                            isCurrentPage = true;
                            break;
                        }
                    }
                }
            }
            if (!isCurrentPage) {
                return self.registration.showNotification(title, options);
            }
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();
    
    const urlToOpen = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
            for (var i = 0; i < windowClients.length; i++) {
                var client = windowClients[i];
                if (client.url === urlToOpen && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});
