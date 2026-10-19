// Service worker do Ryuk: Voo Noturno. Guarda o jogo para abrir sem internet;
// o ranking (/api/) sempre vai à rede. Mudou arquivo do jogo? Suba a VERSAO.
const VERSAO = 'ryuk-v4';
const ARQUIVOS = [
  './', 'index.html', 'manifest.webmanifest', 'ryuk-voando.glb',
  'vendor/three.module.js', 'vendor/addons/loaders/GLTFLoader.js', 'vendor/addons/utils/BufferGeometryUtils.js',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/maskable-512.png', 'icons/apple-180.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin && url.pathname.startsWith('/api/')) return;

  // Página: rede primeiro (pega versão nova), cache se estiver sem internet.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(r => {
      const copia = r.clone();
      caches.open(VERSAO).then(c => c.put('index.html', copia));
      return r;
    }).catch(() => caches.match('index.html')));
    return;
  }

  // Resto (inclusive as fontes do Google): cache primeiro, rede para preencher.
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok || r.type === 'opaque') {
      const copia = r.clone();
      caches.open(VERSAO).then(c => c.put(req, copia));
    }
    return r;
  })));
});
