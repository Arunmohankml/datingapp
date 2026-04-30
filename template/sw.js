self.addEventListener("fetch", function(event) {
  event.respondWith(fetch(event.request));
});

self.addEventListener('push', function(event) {
    console.log('[Service Worker] Push Received.');
    if (event.data) {
        try {
            const data = event.data.json();
            const title = data.title || 'New Message';
            const options = {
                body: data.body || 'You have a new notification',
                icon: data.icon || '/icon-192x192.png',
                badge: '/icon-192x192.png',
                vibrate: [100, 50, 100],
                data: {
                    url: data.url || '/'
                }
            };
            event.waitUntil(self.registration.showNotification(title, options));
        } catch (e) {
            console.error('Error parsing push data:', e);
        }
    }
});

self.addEventListener('notificationclick', function(event) {
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();
    if (event.notification.data && event.notification.data.url) {
        event.waitUntil(clients.openWindow(event.notification.data.url));
    }
});
