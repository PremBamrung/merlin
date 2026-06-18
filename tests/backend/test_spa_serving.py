"""SPA static-serving + client-side-route fallback (api/main.py catch-all).

The built React app is a single bundle whose routes (/feed, /library/:id, …)
are resolved client-side by React Router. On a full reload / direct link the
browser asks the server for that path, so the server must return the SPA shell
(index.html) for client routes — while still 404ing unknown /api/* routes and
missing assets rather than masking them with the shell.

These tests only run when the build output (web/dist) is present; in a no-build
environment (e.g. CI without `npm run build`) they skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

pytestmark = pytest.mark.skipif(
    not _WEB_DIST.is_dir(),
    reason="web/dist not built; run `npm run build` to exercise SPA serving",
)


def _an_asset() -> str:
    """Name of a real file under web/dist/assets (hashed → discovered live)."""
    return next(p.name for p in (_WEB_DIST / "assets").iterdir() if p.is_file())


def test_root_serves_shell(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.parametrize(
    "path",
    ["/library", "/feed", "/library/d9859481-e5ca-4b76-974e-c9afb4d8e8cf"],
)
def test_client_routes_fall_back_to_shell(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # Uncached so a redeploy isn't masked by a stale bundle.
    assert r.headers.get("cache-control") == "no-cache"


def test_real_root_file_served(client):
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert "svg" in r.headers["content-type"]


def test_real_asset_served(client):
    r = client.get(f"/assets/{_an_asset()}")
    assert r.status_code == 200


def test_missing_asset_is_404_not_shell(client):
    r = client.get("/assets/does-not-exist.js")
    assert r.status_code == 404


def test_missing_file_like_path_is_404_not_shell(client):
    # A path that names a file but doesn't exist must 404 — not return the shell
    # with a 200 (which would then break as "Unexpected token <").
    r = client.get("/nope.js")
    assert r.status_code == 404


def test_unknown_api_route_is_json_404_not_shell(client):
    r = client.get("/api/bogus")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert "text/html" not in r.headers["content-type"]


def test_known_api_route_still_works(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
