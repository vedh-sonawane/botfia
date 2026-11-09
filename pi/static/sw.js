/* Botfia service worker — caches the app shell so it loads instantly and can be
   installed. The game API is always fetched from the network. */
const CACHE = 'botfia-v11';
const SHELL = ['/', '/styles.css', '/app.js', '/manifest.json', '/icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) =>
    Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api')) return;          // always live
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
