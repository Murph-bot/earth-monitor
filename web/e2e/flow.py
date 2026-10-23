"""Browser checks against a served build, with the API mocked (no backend needed).

Covers: AC 10/20 (no /v1/aois and no console errors while logged out),
AC 21 (draw logged out -> sign up -> area saved and listed), AC 6 (waking
message within 3 s), AC 14/15 (tap targets >= 44 px, map share, no h-scroll),
AC 16 (title), AC 24 (404 status).

  uv run --with playwright python flow.py http://127.0.0.1:8788 [chrome-path]
"""

import json
import sys

from playwright.sync_api import Route, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"
CHROME = sys.argv[2] if len(sys.argv) > 2 else "/usr/bin/google-chrome"


def _png() -> bytes:
    import struct
    import zlib

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    raw = b"\x00" + b"\x10\x10\x10\xff"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG = _png()
SUMMARY = {
    "region": "thessaly", "bounds": [21.3, 39.0, 23.6, 40.2], "window_days": 7,
    "clear_max_cloud_pct": 20, "generated_at": "2026-10-23T10:00:00Z",
    "greenness": {"mean": 0.41, "previous_mean": 0.44, "delta": -0.03, "areas": 3},
    "rain": {"mean_mm": 12.0, "areas": 3},
    "scenes": {"clear": 3, "cloudy": 2, "latest_scene_at": None},
}

calls: list[tuple[str, str]] = []
created: list[dict] = []
health_up = True


def api(route: Route) -> None:
    req = route.request
    path = req.url.split("/v1", 1)[1].split("?")[0]
    calls.append((req.method, path))

    def ok(body: object, status: int = 200) -> None:
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    if path == "/health":
        return ok({"status": "ok", "db": "ok"}) if health_up else route.abort()
    if path == "/public/region/thessaly/summary":
        return ok(SUMMARY)
    if path == "/auth/register":
        return ok({"token": "tok", "user": {"id": "u", "email": "a@b.co", "display_name": None}}, 201)
    if path == "/aois" and req.method == "POST":
        body = req.post_data_json
        area = {"id": "11111111-1111-1111-1111-111111111111", "name": body["name"], "is_public": False,
                "area_m2": 4.5e7, "bbox": {"minx": 22, "miny": 39, "maxx": 22.1, "maxy": 39.1},
                "created_at": "2026-10-23T10:00:00Z"}
        created.append({**area, "geojson": body["geojson"]})
        return ok(area, 201)
    if path == "/aois":
        items = [{k: v for k, v in a.items() if k != "geojson"} for a in created]
        return ok({"items": items, "total": len(items), "limit": 50, "offset": 0})
    if path.endswith("/scenes"):
        return ok({"items": [], "total": 0, "limit": 50, "offset": 0})
    if path.endswith("/metrics"):
        return ok({"aoi_id": "x", "series": []})
    if path.startswith("/aois/"):
        a = created[0]
        return ok({**{k: v for k, v in a.items() if k != "geojson"},
                   "geom": {"type": "MultiPolygon", "coordinates": []}, "sensor_state": [],
                   "next_pass_estimate": "2026-10-28T10:00:00Z", "next_pass_basis": "revisit_upper_bound"})
    if path == "/notifications":
        return ok({"items": [], "total": 0, "limit": 20, "offset": 0})
    route.fulfill(status=404, content_type="application/json", body="{}")


def main() -> int:
    global health_up
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"])
        for name, vp in (("phone 390", {"width": 390, "height": 844}), ("desktop 1280", {"width": 1280, "height": 800})):
            print(f"--- {name}")
            ctx = b.new_context(viewport=vp)
            pg = ctx.new_page()
            errors: list[str] = []
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(content_type="image/png", body=PNG))
            pg.route("**/v1/**", api)
            calls.clear(); created.clear()

            pg.goto(BASE + "/")
            pg.wait_for_selector("text=What changed this week")
            pg.wait_for_selector("text=0.41")
            check(pg.title().startswith("Kampos"), f"title: {pg.title()}")
            check(not any(p_ == "/aois" for _, p_ in calls), "no /v1/aois call while logged out")
            check(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "no horizontal scroll")
            small = pg.evaluate("""[...document.querySelectorAll('a,button,select,input,summary:not(.maplibregl-ctrl-attrib-button)')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.height<43.5||r.width<43.5)}).map(e=>e.textContent.trim().slice(0,20)+':'+Math.round(e.getBoundingClientRect().height))""")
            check(not small, f"all tap targets >= 44px {small}")
            top = pg.evaluate("document.querySelector('section').getBoundingClientRect().top")
            if vp["width"] < 900:
                check(top / vp["height"] >= 0.6, f"map share above sheet {top / vp['height']:.0%}")
            check("Kampos" in pg.inner_text("header") and "earth-monitor" not in pg.inner_text("body"), "wordmark Kampos, no leftover earth-monitor")

            # draw logged out -> sign up -> area saved
            pg.click("text=Explore the map")
            pg.click("text=Draw an area")
            box = pg.locator("canvas.maplibregl-canvas").bounding_box()
            x0, y0 = box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.25
            pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x0 + 60, y0 + 40, steps=5); pg.mouse.up()
            pg.wait_for_selector("text=Your drawn area")
            pg.click("text=Save this area — free account")
            pg.wait_for_selector("text=✓ Your drawn area is kept")
            check("/signup" in pg.url, "navigated to /signup")
            check(pg.evaluate("sessionStorage.getItem('kampos:pendingAoi')") is not None, "pending polygon in sessionStorage")
            pg.fill("#email", "a@b.co"); pg.fill("#password", "longenough1")
            pg.click("text=Create account & save area")
            pg.wait_for_url("**/areas")
            pg.wait_for_selector("b:has-text('My first area')")
            check(len(created) == 1 and created[0]["name"] == "My first area", "POST /v1/aois with the drawn area")
            check(pg.evaluate("sessionStorage.getItem('kampos:pendingAoi')") is None, "pending cleared after save")
            check(pg.locator("text=Collecting first data").count() > 0 or pg.locator("text=Backfill last 90 days").count() > 0, "empty state shown")
            check(not pg.locator("text=Delete area…").is_visible(), "delete hidden until Area settings opened")
            pg.click("text=Area settings"); pg.click("text=Delete area…")
            check(pg.locator("text=This can't be undone").is_visible(), "delete asks for confirmation")
            pg.click("button:has-text('Cancel')")
            check(pg.locator("b:has-text('My first area')").count() == 1, "cancel leaves the area")
            check(not errors, f"console errors: {errors}")
            ctx.close()

        print("--- waking")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(content_type="image/png", body=PNG))
        health_up = False
        pg.route("**/v1/**", api)
        pg.goto(BASE + "/")
        pg.wait_for_selector("text=Waking up the server", timeout=4500)
        check(True, "waking message within 3 s (+margin)")
        check(pg.locator("canvas.maplibregl-canvas").count() == 1, "map still rendered while waking")
        ctx.close()

        ctx = b.new_context()
        r = ctx.new_page().goto(BASE + "/nope")
        check(r is not None and r.status == 404, f"/nope -> {r.status if r else None}")
        b.close()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
