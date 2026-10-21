const CACHE = 'yimo-shell-v6';
const SHELL = ['/', '/static/styles.css', '/static/reference.css', '/static/app.js', '/static/reference.js', '/static/coach.js', '/static/icon.svg', '/static/manifest.webmanifest', '/api/v1/catalog', '/api/v1/meta', '/api/v1/guidebook'];
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL.map(url => new Request(url, {cache:'reload'})))).then(() => self.skipWaiting())); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('yimo-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== location.origin) return;
  if (!SHELL.includes(url.pathname) && !['/api/v1/catalog', '/api/v1/meta'].includes(url.pathname)) return;
  event.respondWith(fetch(event.request, {cache:'no-cache'}).then(response => {
    if (response.ok) { const copy = response.clone(); event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy))); }
    return response;
  }).catch(async () => (await caches.match(event.request)) || new Response('Offline', {status:503})));
});
