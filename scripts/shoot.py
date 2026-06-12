"""
Screenshot every Merlin page at two widths, for visual verification.

Boots its own Streamlit server against the real DB, drives it with Playwright,
and writes PNGs to ./screenshots/. Run:

    uv run python scripts/shoot.py
    uv run python scripts/shoot.py --item <id>   # also shoot the reader

Inspect the PNGs before declaring any UI work done.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
PORT = 8599
BASE = f"http://localhost:{PORT}"
OUT = ROOT / "screenshots"
WIDTHS = [1280, 1920]

PAGES = [
    ("today", "/"),
    ("ingest", "/ingest"),
    ("library", "/library"),
    ("chat", "/chat"),
    ("insights", "/insights"),
]


def _health_ok() -> bool:
    try:
        return urlopen(f"{BASE}/_stcore/health", timeout=2).status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", help="a knowledge item id, to also shoot the reader")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{ROOT}/data/merlin.db"}
    server = subprocess.Popen(
        ["uv", "run", "streamlit", "run", "app.py",
         "--server.headless", "true", "--server.port", str(PORT)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            if _health_ok():
                break
            time.sleep(1)
        else:
            print("server did not boot", file=sys.stderr)
            return 1

        from playwright.sync_api import sync_playwright

        pages = list(PAGES)
        if args.item:
            pages.append(("reader", f"/library?item={args.item}"))

        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 1080})
                for name, path in pages:
                    page.goto(f"{BASE}{path}", wait_until="networkidle")
                    page.wait_for_timeout(2500)  # let fragments/charts settle
                    out = OUT / f"{name}_{width}.png"
                    page.screenshot(path=str(out), full_page=True)
                    print(f"wrote {out.relative_to(ROOT)}")
                page.close()
            browser.close()
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
