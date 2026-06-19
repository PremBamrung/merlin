# Browser Extension Plan — one-click ingest

A small browser extension to ingest the page you're currently viewing (YouTube
now; Reddit + websites later) directly into Merlin, without opening the app.
Status: **design/feasibility notes**, not yet built.

## Goal

Reduce the friction of ingesting new docs. On desktop, while viewing a YouTube
video (later a Reddit thread or any website), click a toolbar button → the item
is queued for ingestion in Merlin. No tab-switching, no copy-pasting URLs into
the app.

## Why it's easy

The whole ingest path is already a single stateless POST (`api/routers/ingest.py`):

```
POST http://<host>:8000/api/ingest/youtube
{ "url": "...", "languages": [...], "summary_length": "..." }
→ { "task_id": "..." }
```

So the extension only has to grab the active tab's URL and fire that request.
A minimal Manifest V3 extension is ~50 lines:

- `manifest.json` — toolbar button + `host_permissions` for the API host
- a background service worker: `chrome.tabs.query({active:true})` → `fetch(POST)`
- optionally a popup with language / summary-length pickers (or one-click with
  defaults)

The extension stays trivial. **The real work is the future source plugins**
(Reddit/website) under `merlin/knowledge_sources/plugins/<type>/`, not the
extension — YouTube is currently the only registered plugin.

## Deployment context (decided)

- Merlin is **self-hosted on the NAS** (OpenMediaVault, "omv"), reachable at
  `omv:8000`.
- Out of network, devices reach it over **Tailscale**. Tailscale **MagicDNS**
  gives one stable hostname that resolves **both in and out of network** → the
  extension can point at a single base URL (`http://omv:8000`) with no
  home/away branching. The extension inherits the same reachability as the
  browser (Tailscale must be up on the laptop, which it already is to reach the
  frontend).

### Implications

1. **Reachability** — basically solved by Tailscale. Still make the base URL a
   **config field** in the extension options (not hardcoded) so it can point at
   a LAN IP or a different tailnet name without rebuilding.
2. **Auth** — the **tailnet is the auth boundary**. Only devices in the tailnet
   can reach `omv:8000`, and Tailscale handles device identity + encryption. So
   no app-level token is needed. *Add a token only if Merlin is ever exposed
   beyond the tailnet (e.g. Tailscale Funnel).*
3. **Plain HTTP is fine** — Tailscale encrypts at the network layer (WireGuard),
   so `http://omv:8000` is secure despite not being HTTPS. MV3 service-worker
   fetches to `http://` work as long as the host is in `host_permissions` (no
   mixed-content issue — no page context). No TLS certs needed on the NAS just
   for this.
4. **CORS (the one backend change)** — the extension's origin is
   `chrome-extension://<id>`, which is cross-origin to `omv:8000`. Add it to the
   existing `CORS_ORIGINS` env var (already supports comma-separated extras,
   `api/main.py:39`), or switch to `allow_origin_regex` for
   `chrome-extension://.*`. No code restructuring.

## Distribution across personal devices (not public)

Source lives **in this repo** (e.g. `extension/`) — an unpacked extension *is*
just that directory of static files; no build step needed for plain MV3.

### Tier 1 — zero-store, fully private (recommended)

On each device: clone the repo → `chrome://extensions` → enable Developer mode →
"Load unpacked" → point at `extension/`. Update via `git pull` + the refresh
icon on the extension.

- Pros: free, nothing leaves your machines, source stays in-repo, works on any
  Chromium browser (Chrome / Edge / Brave).
- Cons: a dismissable "disable developer-mode extensions" nag on each Chrome
  launch; updates are manual (pull + refresh), not automatic.

### Tier 2 — private listing with auto-update (only if Tier 1 friction annoys)

- **Chrome:** publish as **"Unlisted"** on the Web Store — not public or
  discoverable (install only via direct link), one-click install + auto-update
  on every device. One-time $5 dev fee + Google review.
- **Firefox:** Mozilla **requires signing**, but offers **self-distribution** —
  submit to AMO, choose "On your own" (unlisted), Mozilla signs it, you host the
  signed `.xpi` yourself (repo/NAS) and Firefox auto-updates from `update_url`.
  Not public.

### Trap to avoid

Do **not** use a self-hosted `.crx` + `update_url` for Chrome — Google killed
off-store installs / self-hosted auto-update for normal users; it now works only
via enterprise admin policy. Not worth it for personal use.

### Firefox caveat

Stable Firefox won't permanently load unsigned extensions, so Tier 1
(load-unpacked) is Chromium-only in practice. On Firefox it's either the AMO
self-signing route (Tier 2) or running Developer/ESR edition with signature
enforcement off. **Open question: which browsers are the target devices on?**
That decides whether Tier 1 alone is sufficient.

## Websites: the extension is the *better* ingestion path

For the future website source, the extension can capture the **already-rendered
DOM text** from the tab and POST *that* as the content — sidestepping paywalls,
bot-blocking, and JS-rendered pages that server-side fetching struggles with. So
the website plugin's `IngestRequest` should be designed to **optionally accept
pre-extracted text**, not just a URL.

## Rough build checklist (when we do it)

- [ ] Backend: add the extension origin to CORS (`CORS_ORIGINS` or
      `allow_origin_regex`).
- [ ] `extension/manifest.json` — MV3, toolbar action, `host_permissions` for
      the API host, options page.
- [ ] `extension/background.js` — read active tab URL, POST to
      `/api/ingest/youtube`, surface a success/failure badge or notification.
- [ ] `extension/options.html` + storage — configurable base URL (default
      `http://omv:8000`) and default summary length / languages.
- [ ] `extension/popup.html` (optional) — per-ingest language / summary-length
      overrides.
- [ ] Follow-on (separate work): Reddit + website ingest plugins; for websites,
      accept pre-extracted page text in the ingest envelope.
