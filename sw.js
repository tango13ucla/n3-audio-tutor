const CACHE_NAME = "n3-studio-tutor-v69";
const BUILD_STAMP = "2026-11-25_85e09336753b3b_8eaec1e5_fd9037_22d40f51";
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
      Promise.all(keys.filter(k => k.startsWith("n3-studio-tutor-") && k !== CACHE_NAME).map(k => caches.delete(k)))
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
  if (url.pathname.includes("/api/") || url.pathname.endsWith("daily_radio.mp3") || url.pathname.endsWith(".mp4") || url.pathname.endsWith("daily_radio_meta.json")) return;

  // Network-First with offline fallback for encrypted body_vault.enc (always fresh online, resilient on flights)
  if (url.pathname.endsWith("body_vault.enc")) {
    event.respondWith(
      fetch(req, { cache: "no-store" }).then(res => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put("./body_vault.enc", copy)).catch(() => {});
        }
        return res;
      }).catch(() => caches.match("./body_vault.enc"))
    );
    return;
  }

  // Cache-First keyed by ?v=<hash> for short studio MP3s, icons, story posters, and WebVTT subtitles
  if (url.pathname.endsWith(".mp3") || url.pathname.endsWith(".png") || url.pathname.endsWith(".jpg") || url.pathname.endsWith(".vtt")) {
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

  // Explicit edition-bust (?v=...) always fetches fresh HTML from network first
  if (url.searchParams.has("v") || url.searchParams.has("refresh")) {
    event.respondWith(
      fetch(req, { cache: "no-store" }).then(res => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put("./index.html", copy)).catch(() => {});
        }
        return res;
      }).catch(() => caches.match("./index.html"))
    );
    return;
  }

  // 0ms Instant Launch (Stale-While-Revalidate) for HTML shell & manifest + silent background refresh
  const isDocNav = req.mode === "navigate" || url.pathname.endsWith("/") || url.pathname.endsWith("/index.html");
  event.respondWith(
    caches.open(CACHE_NAME).then(async cache => {
      const matchKey = isDocNav ? "./index.html" : req;
      const cached = await cache.match(matchKey, { ignoreSearch: isDocNav });
      const netFetch = fetch(isDocNav ? "./index.html" : req, { cache: "no-store" })
        .then(res => {
          if (res && res.status === 200) {
            cache.put(matchKey, res.clone()).catch(() => {});
          }
          return res;
        })
        .catch(() => null);
      if (cached) {
        event.waitUntil(netFetch);
        return cached;
      }
      const fresh = await netFetch;
      if (fresh) return fresh;
      return cache.match("./index.html");
    })
  );
});
