"""render_png's cache key quantizes the free-form ?stretch= query param —
otherwise every slightly different float (clients can pass any value in
(0, 10]) busts the in-process LRU and forces a fresh COG read + render."""

import pytest

import app.tiles.render as render_module
from app.tiles.render import render_png


def test_render_png_quantizes_stretch_for_the_cache_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_cached(
        hrefs: tuple[str, ...],
        scale_offsets: tuple[tuple[float, float], ...],
        display_max: float,
        x: int,
        y: int,
        z: int,
    ) -> bytes:
        calls.append(display_max)
        return b"png"

    monkeypatch.setattr(render_module, "_render_png_cached", fake_cached)

    render_png(("h",), ((1.0, 0.0),), 0.301, 0, 0, 0)
    render_png(("h",), ((1.0, 0.0),), 0.304, 0, 0, 0)  # same cache bucket as 0.301
    render_png(("h",), ((1.0, 0.0),), 0.37, 0, 0, 0)

    assert calls == [pytest.approx(0.3), pytest.approx(0.3), pytest.approx(0.35)]
