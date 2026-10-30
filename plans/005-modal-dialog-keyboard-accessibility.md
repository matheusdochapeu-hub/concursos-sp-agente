# Plan 005: Modal Dialog Keyboard Accessibility and Escape Key Handling

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `advisor-plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat aa28286..HEAD -- render_site.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-verification-baseline.md
- **Category**: bug
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

The application provides several rich modal dialogs (`modalComparar`, `modalCompartilhar`, `modalDevStats`, `modalPix`, `modalApp`) marked with `role="dialog"` and `aria-modal="true"`. However, pressing the `Escape` key only closes the filters sidebar (`sidebarFiltros`), leaving all other modals open. This traps keyboard and screen-reader users, violating WCAG 2.1 Success Criterion 2.1.2 (No Keyboard Trap) and common accessibility standards.

## Current state

- In `render_site.py:3760-3763`:
  ```javascript
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebarFiltros && sidebarFiltros.classList.contains('aberto')) {
      fecharSidebarFiltros();
    }
  });
  ```
- All other modal dialogs toggle the CSS class `aberto` on open/close:
  - `modalComparar.classList.remove('aberto')`
  - `modalCompartilhar.classList.remove('aberto')`
  - `modalDevStats.classList.remove('aberto')`
  - `modalPix.classList.remove('aberto')`
  - `modalApp.classList.remove('aberto')`

## Commands you will need

| Purpose   | Command                                         | Expected on success |
|-----------|-------------------------------------------------|---------------------|
| Syntax    | `python -m py_compile render_site.py`           | exit 0              |
| Run tests | `python -m unittest discover -s tests -v`       | `OK`                |

## Scope

**In scope**:
- `render_site.py` (JavaScript event listener section)

**Out of scope**:
- `agente.py`
- HTML modal markup structure

## Git workflow

- Branch: `advisor/005-modal-keyboard-accessibility`
- Commit message: `fix(a11y): add global Escape key dismiss handler for all modal dialogs`

## Steps

### Step 1: Update global `keydown` listener to close all active modals

In `render_site.py`, update the `Escape` handler around line 3760 to dismiss any active modal and the sidebar:

```javascript
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      let modalFechado = false;
      const modaisAbertos = document.querySelectorAll('.modal-bg.aberto, .sidebar-filtros.aberto');
      modaisAbertos.forEach((el) => {
        el.classList.remove('aberto');
        modalFechado = true;
      });
      if (typeof fecharSidebarFiltros === 'function' && sidebarFiltros && sidebarFiltros.classList.contains('aberto')) {
        fecharSidebarFiltros();
        modalFechado = true;
      }
      if (modalFechado) {
        e.preventDefault();
      }
    }
  });
```

**Verify**:
1. Run `python -m py_compile render_site.py`.
2. Open `docs/index.html` in browser.
3. Open the Pix modal, press `Escape` -> modal must close immediately.
4. Open the Share modal, press `Escape` -> modal must close immediately.
5. Open the Compare modal, press `Escape` -> modal must close immediately.

## Done criteria

- [ ] All modals with class `.modal-bg.aberto` close when `Escape` is pressed.
- [ ] Sidebar filters close when `Escape` is pressed.
- [ ] No regression in modal mouse clicks or backdrop clicks.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- If closing modals interferes with form submission or focus restoration in complex browser environments.
