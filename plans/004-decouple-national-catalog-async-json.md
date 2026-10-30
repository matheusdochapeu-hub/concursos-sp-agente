# Plan 004: Decouple National Catalog from HTML into Asynchronous JSON

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `advisor-plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat aa28286..HEAD -- agente.py render_site.py docs/sw.js`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-verification-baseline.md
- **Category**: perf
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

`docs/index.html` is currently 4,038,826 bytes (~4.04 MB). Over 85% of this file (~3.5 MB) consists of raw JSON for 620+ national contests inlined at `render_site.py:3154` (`const CATALOGO_BRASIL = {catalogo_json};`). This national catalog is only used in Aba 5 ("Buscar Cargo Específico"). As a result, users viewing SP Fisioterapia or SP Nível Médio must download 4 MB of data on every load, causing severe mobile loading delay and ballooning the Git repository by ~160 MB every month. Decoupling the national catalog into a separate `docs/data/catalogo_brasil.json` fetched asynchronously shrinks `index.html` to < 500 KB (an ~88% reduction).

## Current state

- In `render_site.py:687`:
  ```python
  catalogo_json = safe_json_for_script(catalogo_brasil)
  ```
- In `render_site.py:3154`:
  ```javascript
  const CATALOGO_BRASIL = {catalogo_json};
  ```
- In `render_site.py:3946, 4546`:
  `CATALOGO_BRASIL` is iterated for counts and filtering in Aba 5.
- The badges in `render_site.py:2648, 2866` already receive the static count `{len(catalogo_brasil)}` via Python interpolation, so the badge count does not require inlining the dataset.

## Commands you will need

| Purpose   | Command                                              | Expected on success |
|-----------|------------------------------------------------------|---------------------|
| Run tests | `python -m unittest discover -s tests -v`            | `OK`                |
| Syntax    | `python -m py_compile agente.py render_site.py`      | exit 0              |
| Check size| `powershell -c "(Get-Item docs/index.html).Length"`  | `< 600000` bytes    |

## Scope

**In scope**:
- `agente.py` (save `docs/data/catalogo_brasil.json`)
- `render_site.py` (replace inline JSON with asynchronous fetch on tab 5 activation)
- `docs/sw.js` (allow caching of `./data/catalogo_brasil.json`)

**Out of scope**:
- Do not alter the filtering logic, search algorithms, or card presentation in Aba 5.
- Do not modify Aba 1, 2, 3 or 4 HTML structures.

## Git workflow

- Branch: `advisor/004-decouple-national-catalog`
- Commit message: `perf: load national catalog asynchronously from JSON to reduce HTML size by 88%`

## Steps

### Step 1: Save `docs/data/catalogo_brasil.json` in `agente.py`

In `agente.py`, near line 1865 (where `RESULTS_FILE` and `HTML_FILE` are saved):
1. Define `DOCS_DATA_DIR = DOCS_DIR / "data"`.
2. Ensure directory exists: `DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)`.
3. Save `catalogo_brasil`:
   ```python
   (DOCS_DATA_DIR / "catalogo_brasil.json").write_text(
       json.dumps(catalogo_brasil, ensure_ascii=False, separators=(",", ":")),
       encoding="utf-8"
   )
   ```

### Step 2: Update `render_site.py` to remove inline JSON injection

In `render_site.py:687`, remove `catalogo_json = safe_json_for_script(catalogo_brasil)`.
In `render_site.py:3154`, replace:
```javascript
  const CATALOGO_BRASIL = {catalogo_json};
```
with:
```javascript
  let CATALOGO_BRASIL = [];
  let catalogoBrasilCarregado = false;
  let carregandoCatalogoBrasil = false;

  async function carregarCatalogoBrasilSeNecessario() {
    if (catalogoBrasilCarregado || carregandoCatalogoBrasil) return;
    carregandoCatalogoBrasil = true;
    const loadingEl = document.getElementById('loadingBuscaCargo');
    if (loadingEl) loadingEl.style.display = 'block';
    try {
      const resp = await fetch('./data/catalogo_brasil.json');
      if (resp.ok) {
        CATALOGO_BRASIL = await resp.json();
        catalogoBrasilCarregado = true;
        if (typeof aplicarFiltrosBuscaCargo === 'function') {
          aplicarFiltrosBuscaCargo();
        }
      }
    } catch (err) {
      console.error('Falha ao carregar catálogo nacional:', err);
    } finally {
      carregandoCatalogoBrasil = false;
      if (loadingEl) loadingEl.style.display = 'none';
    }
  }
```

### Step 3: Trigger loading on Aba 5 activation

In `render_site.py`, in the tab switching event listener for `aba_busca_cargo` / Aba 5 button:
```javascript
  if (abaId === 'aba_busca_cargo') {
    carregarCatalogoBrasilSeNecessario();
  }
```
Also call `carregarCatalogoBrasilSeNecessario()` if the user types or clicks the search input in Aba 5.

### Step 4: Add loading indicator placeholder to Aba 5 section

In `render_site.py`, inside the HTML for the Aba 5 section (near `gridBusca`), add:
```html
<div id="loadingBuscaCargo" style="display:none; text-align:center; padding:2rem; font-weight:600; color:var(--cor-primaria);">
  ⏳ Carregando concursos de todo o Brasil...
</div>
```

**Verify**:
1. Run `python -m py_compile agente.py render_site.py`.
2. Inspect generated `docs/index.html`: file size should drop from ~4 MB to < 550 KB.
3. Verify that Aba 1, 2, 3, 4 render instantly.
4. Verify clicking Aba 5 triggers the fetch and renders the cards.

## Done criteria

- [ ] `docs/data/catalogo_brasil.json` is generated during daily run.
- [ ] `docs/index.html` size is under 600 KB.
- [ ] Aba 5 loads the JSON dynamically and renders search results properly.
- [ ] No regression in other tabs.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- If `fetch('./data/catalogo_brasil.json')` fails on `file://` protocol when running via `rodar_local.bat` without a local web server (Note: modern Chromium browsers block local `fetch()` from `file:///`. If `rodar_local.bat` runs locally, include an embedded fallback or launch a lightweight local server: `python -m http.server -d docs 8080`).
