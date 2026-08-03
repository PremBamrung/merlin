"""Screenshot and sanity-check a standalone page — a mockup, a spec, a preview.

The fork of shoot.py for things that are not the running app. Takes a local file
or any URL, so it works on the self-contained `design-direction-*.html` pages
(fonts embedded as base64, no build step, opens from disk).

    uv run python web/scripts/shoot_page.py design-direction-v6.html --fonts 3
    uv run python web/scripts/shoot_page.py https://example.com --out /tmp/shots

Beyond capturing, it asserts the things that are easy to break and hard to see:

* **no horizontal scroll** — both that `scrollWidth == clientWidth` and that
  `scrollTo(9999, 0)` doesn't move, since a stray wide child scrolls the document
  even when the numbers look fine. Wide content is supposed to scroll inside its
  own `overflow-x: auto` container, not drag the page.
* **no console errors, no failed requests.**
* **the fonts actually loaded** (`--fonts N`). A specimen that silently falls back
  to a system face invalidates the whole page — a design round was once rejected
  on the strength of Georgia standing in for the real typeface.

Exit code is non-zero if any case fails, so it can gate a loop. It still isn't a
substitute for opening the PNGs: a page can pass every assertion here while a
drawing inside it is visually wrong.
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "screenshots"
DEFAULT_CASES = [(1280, 1400), (390, 1600)]

PROBE = """() => {
  const de = document.documentElement;
  const before = window.scrollX;
  window.scrollTo(9999, 0);
  const moved = window.scrollX !== before;
  window.scrollTo(0, 0);
  const faces = [...document.fonts];
  return {
    overflow: de.scrollWidth - de.clientWidth,
    moved,
    families: [...new Set(faces.map(f => f.family))].sort(),
    loaded: faces.filter(f => f.status === 'loaded').length,
  };
}"""


def target_url(raw: str) -> str:
    if "://" in raw:
        return raw
    path = Path(raw).resolve()
    if not path.exists():
        raise SystemExit(f"no such page: {path}")
    return path.as_uri()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("page", help="path to an html file, or a URL")
    ap.add_argument("--fonts", type=int, default=0, help="expected loaded font faces")
    ap.add_argument(
        "-w", "--width", action="append", type=int, metavar="PX",
        help=f"viewport width, repeatable; default {[w for w, _ in DEFAULT_CASES]}",
    )
    ap.add_argument("--scheme", choices=["light", "dark", "both"], default="both")
    ap.add_argument("--prefix", help="screenshot name prefix [derived from filename]")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"[{DEFAULT_OUT}]")
    args = ap.parse_args()

    url = target_url(args.page)
    stem = Path(args.page).stem or "page"
    prefix = args.prefix or stem.replace("design-direction-", "")
    cases = [(w, 1400) for w in args.width] if args.width else DEFAULT_CASES
    schemes = ["light", "dark"] if args.scheme == "both" else [args.scheme]
    args.out.mkdir(parents=True, exist_ok=True)

    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in cases:
            for scheme in schemes:
                ctx = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme=scheme,
                    device_scale_factor=2,
                )
                page = ctx.new_page()
                errors: list[str] = []
                bad_req: list[str] = []
                page.on(
                    "console",
                    lambda m: errors.append(m.text) if m.type == "error" else None,
                )
                page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                page.on("requestfailed", lambda r: bad_req.append(r.url))

                page.goto(url, wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                r = page.evaluate(PROBE)

                ok = (
                    r["overflow"] <= 0
                    and not r["moved"]
                    and not errors
                    and not bad_req
                    and (not args.fonts or r["loaded"] == args.fonts)
                )
                failed += not ok
                tag = f"{width}-{scheme}"
                print(
                    f"  {'✓' if ok else '✕'} {tag:<12} "
                    f"overflow={r['overflow']} scrolled={r['moved']} "
                    f"fonts={r['families']} loaded={r['loaded']} "
                    f"consoleErr={len(errors)} failedReq={len(bad_req)}"
                )
                for e in errors[:3]:
                    print(f"      {e}")

                page.screenshot(path=str(args.out / f"{prefix}-{tag}.png"), full_page=True)
                ctx.close()
        browser.close()

    print("all cases passed" if not failed else f"{failed} case(s) failed")
    print(f"PNGs in {args.out} — open them, the assertions don't see drawings.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
