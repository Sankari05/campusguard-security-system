// RIDGEWATCH Service Worker for Android Companion Notification Delivery
// Enables native Android OS system notifications for smartwatch notification mirroring.

const CACHE_NAME = 'ridgewatch-bridge-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Handle incoming notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const clickActionUrl = '/frontend/bridge.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if (client.url.includes('bridge.html') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(clickActionUrl);
      }
    })
  );
});

// Handle push notification events if backend Web Push is triggered
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: '🚨 RIDGEWATCH EMERGENCY ALERT', body: event.data.text() };
    }
  }
  const title = data.title || '🚨 RIDGEWATCH — GO';
  const options = {
    body: data.body || 'Survivor detected. Proceed to rescue location.',
    icon: '/frontend/img/alert-icon.png',
    badge: '/frontend/img/badge.png',
    tag: data.command_id || 'RIDGEWATCH-EMERGENCY',
    vibrate: [500, 200, 500, 200, 500],
    requireInteraction: true,
    data: data,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
