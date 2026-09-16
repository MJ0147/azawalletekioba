// EKIOBA service worker. It makes the site installable as an app and, when the device is offline,
// shows the last home page it saw. It never caches API calls, chat or payments, which must be live.
const CACHE = 'ekioba-shell-v1';
const SHELL = ['/', '/static/css/styles.css', '/static/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  // Only page loads get an offline fallback; everything else goes straight to the network.
  if (request.method !== 'GET' || request.mode !== 'navigate') return;
  event.respondWith(
    fetch(request).catch(() => caches.match('/').then((page) => page || Response.error()))
  );
});
