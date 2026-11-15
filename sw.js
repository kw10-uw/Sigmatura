// Sigmatura service worker: app works offline after the first visit.
// Bump VERSION on every release so phones pick up the new files.
const VERSION = "v3";
const CACHE = "sigmatura-" + VERSION;
// Formula sheet pages (maths): precached so they open offline, e.g. during practice without signal.
const WZORY = Array.from({ length: 31 }, (_, i) => `assets/wzory/p${String(i + 4).padStart(2, "0")}.webp`);
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon.svg", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png", ...WZORY];

// Real CKE tasks: the exam files listed in content/exams/index.json and the images they use.
async function examFiles() {
  try {
    const list = await (await fetch("content/exams/index.json", { cache: "no-cache" })).json();
    const out = ["content/exams/index.json"];
    for (const f of list) {
      out.push("content/exams/" + f);
      const ex = await (await fetch("content/exams/" + f, { cache: "no-cache" })).json();
      for (const m of ex.materials || []) if (m.file) out.push("content/" + m.file);
    }
    return out;
  } catch (e) { return []; }
}

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(async c => {
    await c.addAll(SHELL);
    await c.addAll(await examFiles()).catch(() => {});   // exam images are a bonus: the app still works without them
  }).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Network first (so updates arrive when online), cache as offline fallback.
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match("index.html")))
  );
});
