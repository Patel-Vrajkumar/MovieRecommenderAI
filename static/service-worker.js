self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('movies-ai-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/static/style.css',
        '/static/Loader.css',
        '/static/script.js',
      ]);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
