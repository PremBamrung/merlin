"""Screenshot the v3 web app routes at two widths for visual verification.

Assumes the Vite dev server (:5173) and the API (:8000) are already running.
Run from the repo root:  uv run python web/scripts/shoot.py [--item <id>]

Inspect the PNGs in web/screenshots/ before declaring any UI work done.
"""

import argparse
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = Path(__file__).resolve().parent.parent / "screenshots"
# Baseline + 27" (2560) + 32" (3840) so wide-display layout is verified.
WIDTHS = [1440, 2560, 3840]

PAGES = [
    ("today", "/"),
    ("library", "/library"),
    ("inbox", "/inbox"),
    ("chat", "/chat"),
    ("insights", "/insights"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", help="also shoot the reader for this item id")
    ap.add_argument("--width", type=int, help="only this width")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    pages = list(PAGES)
    if args.item:
        pages.append(("reader", f"/library/{args.item}"))
    widths = [args.width] if args.width else WIDTHS

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, path in pages:
            for w in widths:
                page = browser.new_page(viewport={"width": w, "height": 900})
                page.goto(BASE + path, wait_until="networkidle")
                page.wait_for_timeout(900)
                out = OUT / f"{name}_{w}.png"
                page.screenshot(path=str(out), full_page=True)
                print(f"  ✓ {out.relative_to(OUT.parent)}")
                page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
