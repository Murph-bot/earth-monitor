import numpy as np

from app.tiles.render import SCALE_HEX, SCALE_RGB, ramp_rgba


def _rgb(h: str) -> list[int]:
    return [int(h[i : i + 2], 16) for i in (1, 3, 5)]


def test_ramp_endpoints_are_s0_and_s5() -> None:
    out = ramp_rgba(np.array([[0.0, 0.8]]), 0.0, 0.8, np.ones((1, 2), dtype=bool))
    assert out[0, 0, :3].tolist() == _rgb(SCALE_HEX[0])
    assert out[0, 1, :3].tolist() == _rgb(SCALE_HEX[-1])
    assert out[..., 3].tolist() == [[255, 255]]


def test_ramp_hits_each_stop_and_clips() -> None:
    vals = np.linspace(0, 0.8, 6)
    out = ramp_rgba(vals[None, :], 0.0, 0.8, np.ones((1, 6), dtype=bool))
    assert out[0, :, :3].tolist() == SCALE_RGB.astype(int).tolist()
    clipped = ramp_rgba(np.array([[-1.0, 9.0]]), 0.0, 0.8, np.ones((1, 2), dtype=bool))
    assert clipped[0, 0, :3].tolist() == _rgb(SCALE_HEX[0])
    assert clipped[0, 1, :3].tolist() == _rgb(SCALE_HEX[-1])


def test_invalid_pixels_are_transparent() -> None:
    out = ramp_rgba(np.array([[0.4, 0.4]]), 0.0, 0.8, np.array([[True, False]]))
    assert out[0, :, 3].tolist() == [255, 0]
