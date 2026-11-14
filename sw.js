const CACHE_NAME = "n3-audio-tutor-v2";

self.addEventListener("install", event => {
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || event.request.headers.has("range")) return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
