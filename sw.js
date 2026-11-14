const CACHE_NAME = "n3-studio-tutor-v19";
const CORE_SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      Promise.all(
        CORE_SHELL.map(url =>
          fetch(url, { cache: "no-store" })
            .then(res => (res && res.ok ? cache.put(url, res) : null))
            .catch(() => {})
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("message", event => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET" || req.headers.has("range")) return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/") || url.pathname.endsWith("daily_radio.mp3")) return;

  // Cache-First keyed by ?v=<hash> for short studio MP3s and icons, fetching fresh from network on cache miss
  if (url.pathname.endsWith(".mp3") || url.pathname.endsWith(".png")) {
    event.respondWith(
      caches.match(req).then(cached => {
        if (cached) return cached;
        return fetch(req, { cache: "no-store" }).then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, copy)).catch(() => {});
          }
          return res;
        });
      })
    );
    return;
  }

  // Fresh Network-First for HTML & manifest
  event.respondWith(
    fetch(req, { cache: "no-store" }).then(res => {
      if (res && res.status === 200) {
        const copy = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(req).then(r => r || caches.match("./index.html")))
  );
});
