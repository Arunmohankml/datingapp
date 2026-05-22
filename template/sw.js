self.addEventListener("fetch", function(event) {
  event.respondWith(fetch(event.request));
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
        icon: '/icon-192x192.png',
        badge: '/icon-192x192.png',
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
