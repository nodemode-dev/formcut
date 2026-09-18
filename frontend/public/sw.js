// Minimal service worker for installability: the app shell is cached on
// install and served network-first, so the engine's live API is never
// interposed and a cold offline open still shows the shell.
const SHELL = "formcut-shell-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/"])));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(SHELL).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || caches.match("/")))
  );
});
