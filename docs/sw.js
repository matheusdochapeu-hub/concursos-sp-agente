// Service Worker — Concursos
// Estratégia: rede primeiro (para pegar a atualização diária) e cache como reserva offline.
// Só intercepta a própria origem: OAuth do Google e planilha da contagem passam direto.
const CACHE_NAME = "concursos-sp-v24";
const OFFLINE_FALLBACK = "./index.html";
const ASSETS = [
  "./",
  "./index.html",
  "./privacidade.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-512-maskable.png",
  "./apple-touch-icon.png",
  "./favicon.ico"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // addAll falha inteiro se um asset faltar: adiciona um por um e segue.
      .then((cache) => Promise.allSettled(ASSETS.map((url) => cache.add(url))))
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

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const reqUrl = new URL(event.request.url);
  if (reqUrl.origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && response.type === "basic") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone)).catch(() => {});
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        // Navegação offline sem cache exato: devolve o app.
        if (event.request.mode === "navigate") {
          const shell = await caches.match(OFFLINE_FALLBACK);
          if (shell) return shell;
        }
        return new Response("Offline", { status: 503, statusText: "Offline" });
      })
  );
});
