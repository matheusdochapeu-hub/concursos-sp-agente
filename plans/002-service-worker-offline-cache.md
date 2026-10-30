# Plan 002: Fix Service Worker Offline Pre-Caching and Activation Lifecycle

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `advisor-plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat aa28286..HEAD -- docs/sw.js`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-verification-baseline.md
- **Category**: bug
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

The application is configured as an installable Progressive Web App (PWA) with a manifest and service worker. However, the service worker currently never caches the declared assets during installation, and indiscriminately deletes all cache storages upon activation (including the active cache version). If an installed user opens the app without internet access or loses connectivity, the service worker fails to serve `index.html` from cache, showing the browser's default offline error screen.

## Current state

- In `docs/sw.js:1-21`:
  ```javascript
  const CACHE_NAME = "concursos-sp-v20";
  const ASSETS = [
    "./",
    "./index.html",
    "./manifest.webmanifest",
    "./icon-192.png",
    "./icon-512.png"
  ];

  self.addEventListener("install", (event) => {
    self.skipWaiting();
  });

  self.addEventListener("activate", (event) => {
    event.waitUntil(
      caches.keys().then((keys) =>
        Promise.all(keys.map((k) => caches.delete(k)))
      )
    );
    self.clients.claim();
  });
  ```
- Issues:
  1. `install` event does not call `caches.open(CACHE_NAME).then(c => c.addAll(ASSETS))`. The `ASSETS` array is completely unused.
  2. `activate` deletes `keys.map(k => caches.delete(k))` without checking `k !== CACHE_NAME`. It deletes the active cache immediately upon activation.

## Commands you will need

| Purpose         | Command                                                | Expected on success |
|-----------------|--------------------------------------------------------|---------------------|
| Syntax check JS | `node -c docs/sw.js` (or inspect via browser DevTools) | exit 0              |
| Unit tests      | `python -m unittest discover -s tests -v`              | all pass            |

## Scope

**In scope**:
- `docs/sw.js`

**Out of scope**:
- `docs/manifest.webmanifest`
- `agente.py`
- `render_site.py`

## Git workflow

- Branch: `advisor/002-service-worker-offline-cache`
- Commit message: `fix(pwa): pre-cache assets on install and preserve active cache on activate`

## Steps

### Step 1: Update `install` and `activate` listeners in `docs/sw.js`

1. Bump `CACHE_NAME` to `"concursos-sp-v21"`.
2. Update the `install` event listener to populate the cache with `ASSETS`:
   ```javascript
   self.addEventListener("install", (event) => {
     event.waitUntil(
       caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
     );
     self.skipWaiting();
   });
   ```
3. Update the `activate` event listener to delete ONLY previous/stale cache versions:
   ```javascript
   self.addEventListener("activate", (event) => {
     event.waitUntil(
       caches.keys().then((keys) =>
         Promise.all(
           keys
             .filter((k) => k !== CACHE_NAME)
             .map((k) => caches.delete(k))
         )
       )
     );
     self.clients.claim();
   });
   ```

**Verify**: Run `node -c docs/sw.js` to ensure valid JavaScript syntax.

## Test plan

- Test case 1: In a local browser or DevTools Application tab, register the Service Worker and confirm that under Cache Storage -> `concursos-sp-v21`, all 5 assets (`./`, `./index.html`, `./manifest.webmanifest`, `./icon-192.png`, `./icon-512.png`) are present.
- Test case 2: Toggle "Offline" in DevTools Network tab and refresh the page. The app must render `index.html` completely without any network errors.
- Test case 3: Simulate activating a new service worker version (`v22`) and verify that only `v21` is deleted while `v22` remains.

## Done criteria

- [ ] `docs/sw.js` has `install` handler populating `CACHE_NAME` with `ASSETS`.
- [ ] `docs/sw.js` has `activate` handler filtering `k !== CACHE_NAME`.
- [ ] `CACHE_NAME` is bumped to `concursos-sp-v21`.
- [ ] No files outside `docs/sw.js` are modified.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- If relative paths in `ASSETS` fail during `cache.addAll()` due to subfolder hosting differences on GitHub Pages. (Paths are `./`, `./index.html`, which match `scope: "./"`, so they resolve properly).
