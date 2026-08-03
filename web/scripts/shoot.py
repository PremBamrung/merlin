"""Screenshot the running Merlin SPA so frontend work can be checked by eye.

Playwright is already a project dependency — never `npm i playwright`.
Assumes the Vite dev server and the API are running. From the repo root:

    uv run python web/scripts/shoot.py                     # every route, 390 + 1440
    uv run python web/scripts/shoot.py -r feed -r reader   # just these
    uv run python web/scripts/shoot.py -w 2560 --scheme both
    uv run python web/scripts/shoot.py --base http://localhost:5199

PNGs land in web/screenshots/ as <route>_<width>[_<scheme>].png. Open them —
types and a clean build say nothing about layout, and assertions miss things a
glance catches immediately.

Two traps this script guards against, both of which have already cost a session:

* **Port 5173 is a different project on this machine.** The default base URL is
  still :5173 because that is what `npm run dev` prints, but every page is
  checked for a Merlin-looking title and the run aborts loudly if it isn't one.
  Start Merlin elsewhere with `npm run dev -- --port 5199 --strictPort`.
* **:8000 serves the built SPA but deep routes 404 on a hard load** (StaticFiles
  only falls back at /). Shoot the dev server, not the bundle.
"""

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

DEFAULT_BASE = "http://localhost:5173"
DEFAULT_API = "http://localhost:8000"
OUT = Path(__file__).resolve().parent.parent / "screenshots"

# 390 is the phone case the design system is repeatedly caught out by; 1440 is
# the baseline. Wide displays (2560/3840) are opt-in via -w.
DEFAULT_WIDTHS = [390, 1440]

# name -> path. ":item" is substituted with a real item id (see resolve_item).
ROUTES: dict[str, str] = {
    "feed": "/feed",
    "library": "/library",
    "reader": "/library/:item",
    "topics": "/topics",
    "chat": "/chat",
    "insights": "/insights",
}


def resolve_item(api: str) -> str | None:
    """Grab any item id so the reader route can be shot without being told one."""
    try:
        with urllib.request.urlopen(f"{api}/api/items?limit=1", timeout=5) as r:
            import json

            payload = json.load(r)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"  ! could not reach the API for an item id ({exc})")
        return None
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not items:
        return None
    return str(items[0].get("id"))


def looks_like_merlin(page) -> bool:
    """Cheap guard against shooting whatever else is squatting on the port."""
    title = (page.title() or "").lower()
    if "merlin" in title:
        return True
    # The SPA sets the title per route, so fall back to the shell's own markup.
    return page.locator("[data-app='merlin'], #root").count() > 0 and "vite" not in title


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"dev server [{DEFAULT_BASE}]")
    ap.add_argument("--api", default=DEFAULT_API, help=f"API for item lookup [{DEFAULT_API}]")
    ap.add_argument(
        "-r", "--route", action="append", choices=sorted(ROUTES), metavar="NAME",
        help=f"route to shoot, repeatable; default all ({', '.join(sorted(ROUTES))})",
    )
    ap.add_argument(
        "-w", "--width", action="append", type=int, metavar="PX",
        help=f"viewport width, repeatable; default {DEFAULT_WIDTHS}",
    )
    ap.add_argument("--scheme", choices=["light", "dark", "both"], default="dark")
    ap.add_argument("--item", help="item id for the reader route (default: autodetect)")
    ap.add_argument(
        "--reader-direct", action="store_true",
        help="load the reader by URL instead of clicking through the Library. The "
             "mobile header overflow only reproduces when prev/next exist, i.e. "
             "when you arrive from the list — so the default is the click-through.",
    )
    ap.add_argument("--viewport-only", action="store_true", help="no full-page capture")
    ap.add_argument("--out", type=Path, default=OUT, help=f"output dir [{OUT}]")
    args = ap.parse_args()

    names = args.route or list(ROUTES)
    widths = args.width or DEFAULT_WIDTHS
    schemes = ["light", "dark"] if args.scheme == "both" else [args.scheme]
    args.out.mkdir(parents=True, exist_ok=True)

    item = args.item
    if "reader" in names and not item:
        item = resolve_item(args.api)
        if not item:
            print("  ! no item id — skipping the reader route")
            names = [n for n in names if n != "reader"]

    shots = errors = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in schemes:
            for width in widths:
                ctx = browser.new_context(
                    viewport={"width": width, "height": 900}, color_scheme=scheme
                )
                page = ctx.new_page()
                console: list[str] = []
                page.on(
                    "console",
                    lambda m: console.append(m.text) if m.type == "error" else None,
                )
                page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))

                for name in names:
                    path = ROUTES[name].replace(":item", item or "")
                    console.clear()
                    try:
                        if name == "reader" and not args.reader_direct:
                            page.goto(f"{args.base}/library", wait_until="networkidle")
                            link = page.locator(f"a[href='/library/{item}']").first
                            if link.count():
                                link.click()
                                page.wait_for_url(f"**/library/{item}")
                            else:
                                page.goto(args.base + path, wait_until="networkidle")
                        else:
                            page.goto(args.base + path, wait_until="networkidle")
                        page.wait_for_timeout(900)
                    except PlaywrightError as exc:
                        print(f"  ✕ {name}_{width} — {str(exc).splitlines()[0]}")
                        errors += 1
                        continue

                    if not looks_like_merlin(page):
                        print(
                            f"\n  ✕ {args.base} does not look like Merlin "
                            f"(title: {page.title()!r}).\n"
                            f"    Port 5173 is another project on this machine — "
                            f"start Merlin with:\n"
                            f"    cd web && npm run dev -- --port 5199 --strictPort\n"
                            f"    then re-run with --base http://localhost:5199"
                        )
                        browser.close()
                        return 2

                    suffix = f"_{scheme}" if len(schemes) > 1 else ""
                    out = args.out / f"{name}_{width}{suffix}.png"
                    page.screenshot(path=str(out), full_page=not args.viewport_only)
                    shots += 1
                    note = f"  ({len(console)} console errors)" if console else ""
                    print(f"  ✓ {out.relative_to(args.out.parent)}{note}")
                    for line in console[:2]:
                        print(f"      {line}")
                    errors += bool(console)

                ctx.close()
        browser.close()

    print(f"\n{shots} screenshot(s) in {args.out}. Look at them.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
