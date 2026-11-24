from __future__ import annotations

import cv2
import numpy as np

from vars_gridview.lib.vision.display_adjust import brightness_contrast


def _lab(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)


def _warm_dim_image() -> np.ndarray:
    """Dim, warm (sediment-like) gradient with a black border."""
    rng = np.random.default_rng(0)
    ramp = np.linspace(20, 120, 64, dtype=np.float32)[None, :, None]
    tint = np.array([0.7, 0.9, 1.1], np.float32)  # BGR: warm
    img = np.clip(ramp * tint + rng.normal(0, 4, (64, 64, 3)), 0, 255).astype(np.uint8)
    img[:6] = 0  # letterbox bar
    return img


def test_neutral_settings_return_the_image_unchanged() -> None:
    img = _warm_dim_image()
    assert brightness_contrast(img, 0, 1.0) is img


def test_contrast_keeps_colour_and_spreads_lightness() -> None:
    img = _warm_dim_image()
    out = brightness_contrast(img, 0, 1.5)
    before, after = _lab(img[6:]), _lab(out[6:])  # the picture, not the border

    spread = lambda lab: np.percentile(lab[:, 0], 95) - np.percentile(lab[:, 0], 5)
    assert spread(after) > 1.3 * spread(before)
    # Colour unchanged: it used to turn dim warm areas red and saturate.
    assert abs(after[:, 1].mean() - before[:, 1].mean()) < 1.5
    assert abs(after[:, 2].mean() - before[:, 2].mean()) < 1.5
    # Pivots on the image's own mean: overall lightness about the same.
    assert abs(after[:, 0].mean() - before[:, 0].mean()) < 4


def test_contrast_keeps_black_borders_black() -> None:
    img = _warm_dim_image()
    out = brightness_contrast(img, 0, 1.5)
    assert out[:6].max() == 0  # the old per-channel version turned them grey


def test_brightness_lifts_lightness_only() -> None:
    img = _warm_dim_image()
    before, after = _lab(img), _lab(brightness_contrast(img, 30, 1.0))
    assert after[:, 0].mean() - before[:, 0].mean() > 25
    assert abs(after[:, 1].mean() - before[:, 1].mean()) < 1.5
    assert abs(after[:, 2].mean() - before[:, 2].mean()) < 1.5
