// Minimal service worker (SPEC §15): enough for the site to be installable,
// no offline mode. Every request goes to the network; nothing is cached, so
// a deploy is visible on the next load and protected files are never stored.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => {
  /* pass-through: the browser fetches as usual */
})
