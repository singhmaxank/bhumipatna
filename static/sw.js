const CACHE_NAME = "bhumi-patna-v1";
const APP_SHELL = [
  "/static/img/bhumi_logo.png",
  "/static/css/style.css",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Cache-first for the static app shell only; everything else (HTML pages,
// API calls) always goes to the network so data stays current.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (APP_SHELL.some((path) => url.pathname === path)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});

// Push notifications: admins get notified when a donation needs approval,
// volunteers get notified when their donation is approved, and everyone
// gets notified about new announcements/missions.
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "Bhumi Patna Portal", body: event.data ? event.data.text() : "" };
  }

  const title = data.title || "Bhumi Patna Portal";
  const options = {
    body: data.body || "",
    icon: "/static/img/bhumi_logo.png",
    badge: "/static/img/bhumi_logo.png",
    data: { url: data.url || "/" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if (client.url.endsWith(url) && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(url);
    })
  );
});
