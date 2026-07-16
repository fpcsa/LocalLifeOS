/* LocalLife OS application-shell service worker. User API responses are never cached. */
const CACHE_VERSION = "locallife-shell-v1";
const SHELL_ROUTES = new Set([
  "/",
  "/automation",
  "/calendar",
  "/capacity",
  "/commitments",
  "/finance",
  "/goals",
  "/imports",
  "/notes",
  "/offline",
  "/scenarios",
  "/settings",
  "/tasks",
  "/timeline",
]);
const PRECACHE = ["/", "/offline", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function navigationResponse(request, url) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const response = await fetch(request);
    if (response.ok && SHELL_ROUTES.has(url.pathname) && !url.search) {
      await cache.put(url.pathname, response.clone());
    }
    return response;
  } catch {
    return (await cache.match(url.pathname)) || (await cache.match("/offline")) || Response.error();
  }
}

async function localAssetResponse(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_VERSION);
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // API calls, including loopback calls on :8000, remain network-only and outside Cache Storage.
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (request.mode === "navigate") {
    event.respondWith(navigationResponse(request, url));
    return;
  }
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname === "/icon.svg" ||
    request.destination === "style" ||
    request.destination === "script" ||
    request.destination === "font" ||
    request.destination === "image"
  ) {
    event.respondWith(localAssetResponse(request));
  }
});
