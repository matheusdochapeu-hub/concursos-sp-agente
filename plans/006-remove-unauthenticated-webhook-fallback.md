# Plan 006: Remove Hardcoded Apps Script Webhook Fallback from Public Client Bundle

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

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-verification-baseline.md
- **Category**: security
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

`render_site.py:551` hardcodes an active Google Apps Script webhook URL as a fallback when `AUDIT_WEBHOOK_URL` is unset. This public webhook receives unauthenticated HTTP POST and `sendBeacon` requests containing visitor data (user-agent, login timestamp, visitor name, and email). Hardcoding this in public client-side JavaScript exposes the developer's Apps Script endpoint to quota exhaustion attacks, and transmits visitor telemetry without an explicit privacy policy or opt-in.

## Current state

- In `render_site.py:548-552`:
  ```python
  AUDIT_WEBHOOK_URL = (
      _os.environ.get("AUDIT_WEBHOOK_URL", "").strip()
      or "https://script.google.com/macros/s/AKfycby4DRby4jG-nE9V9c4IGcFgpI14U7Jc76eQy0fQww-ME0AJDCOq9bGcmhxN-0ETnYtJbw/exec"
  )
  ```
- In client-side JS (`render_site.py:5469-5473`):
  ```javascript
  async function enviarRegistroAcessoGlobal(nomeStr, emailStr, eventoStr) {
    try {
      const webhookUrl = obterAuditWebhookUrl();
      if (!webhookUrl) return;
      ...
  ```
- The client-side code already safely no-ops if `webhookUrl` is empty (`if (!webhookUrl) return;`), so removing the hardcoded fallback is completely backwards-compatible and causes no errors.

## Commands you will need

| Purpose   | Command                                         | Expected on success |
|-----------|-------------------------------------------------|---------------------|
| Syntax    | `python -m py_compile render_site.py`           | exit 0              |
| Run tests | `python -m unittest discover -s tests -v`       | `OK`                |

## Scope

**In scope**:
- `render_site.py`

**Out of scope**:
- `agente.py`
- Local developer panel statistics modal

## Git workflow

- Branch: `advisor/006-remove-webhook-fallback`
- Commit message: `sec(audit): remove hardcoded telemetry webhook fallback from client bundle`

## Steps

### Step 1: Remove hardcoded Apps Script webhook URL

In `render_site.py:548-552`, change `AUDIT_WEBHOOK_URL` to only take the value from `os.environ`:
```python
AUDIT_WEBHOOK_URL = _os.environ.get("AUDIT_WEBHOOK_URL", "").strip()
```

### Step 2: Ensure developer panel can still configure a private webhook URL

In `render_site.py`, ensure `obterAuditWebhookUrl()` continues to support `localStorage.getItem(AUDIT_WEBHOOK_KEY)`, so a developer who wishes to collect telemetry can enter their endpoint via the Developer Panel interface without exposing it in the public repository code.

**Verify**:
1. Run `python -m py_compile render_site.py`.
2. Inspect generated HTML to confirm no Apps Script URL is present in the output bundle when the environment variable is unset.

## Done criteria

- [ ] Hardcoded Apps Script URL removed from `render_site.py`.
- [ ] Client bundle does not expose a public telemetry endpoint by default.
- [ ] Developer panel retains ability to set custom webhook via `localStorage`.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- None.
