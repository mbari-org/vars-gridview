"""Display-only image adjustments for ROI tiles and the full-frame view.

Nothing here touches stored data: labels, boxes and embeddings always use the
original pixels. Ported from mbari-ml's review GUI (``mbariml.gui.colour``,
``mbariml.gui.fringes`` and its tile sharpening), where each step was tuned on
MBARI ROV, i2MAP and Coral Observatory imagery.

Colour correction (``ColourCorrector``), per image:

  1. Red compensation (Ancuti et al. 2018): ``r += (mean_g - mean_r) * (1 - r) * g``.
     Red is rebuilt from green, which survives water far better, instead of
     multiplying a weak, noisy red channel. It vanishes when red isn't weak.
  2. Gray-world white balance at 0.85 strength (log-gain), gains clamped to
     0.5-3x, aimed at a slightly warm grey. Full strength turns open water
     pink; neutral grey leaves sediment lavender. Clipped and near-black
     pixels (overlays, borders) don't vote.
  3. One contrast stretch on luminance, the same for every channel so it
     can't shift hue, gain capped at 3x so flat frames aren't turned into
     amplified noise, then a gamma (>= 0.6) that lifts a dark frame's median
     toward mid-grey. The top 0.5% maps to 92% white so bright sand doesn't
     blow out.
  4. A 1.15x saturation boost, and CLAHE on lightness only when "Local
     contrast" is turned up (off by default: it raises object contrast ~40%
     but fine grain ~55%).

Steps 1-3 reduce to lookup tables, so applying them costs about one LUT pass.

The parameters are best measured on the whole frame (a crop's own average is
pulled toward grey). GridView gets tiles as server-side crops, so a tile is
measured on its crop until the full frame has been seen -- e.g. when it is
clicked and shown in the image view -- after which every tile from that frame
uses the frame's parameters (``remember_frame``).

``fix_fringes`` shifts red and blue back onto green (ECC on gradient
magnitude, kept only if it measurably reduces fringing) and median-filters
chroma near edges -- ~10-25 ms per crop.

``sharpen`` is an adaptive unsharp mask on lightness whose radius follows the
thumbnail's enlargement and whose amount fades out where detail is no
stronger than the crop's own noise.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

import cv2
import numpy as np

# -- colour correction --------------------------------------------------------

WB_STRENGTH = 0.85
WARM = np.array([0.92, 1.0, 1.04], np.float32)  # BGR gains on top of gray-world
TOP = 0.92  # where the brightest 0.5% lands after the contrast stretch
MAX_CONTRAST_GAIN = 3.0
SATURATION = 1.15
MAX_REMEMBERED_FRAMES = 20_000  # (7,) float32 each: ~1 MB at the cap
_LUMA = np.array([0.114, 0.587, 0.299], np.float32)  # BGR


def _compensate_red(red: np.ndarray, green: np.ndarray, k: float) -> np.ndarray:
    return red + k * (1.0 - red) * green


def measure_pixels(bgr: np.ndarray) -> np.ndarray:
    """(7,) colour parameters ``[k, gain_b, gain_g, gain_r, lo, scale, gamma]``
    measured on *bgr* (downscaled internally to <= 256 px a side)."""
    scale = 256 / max(bgr.shape[:2])
    small = (
        cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else bgr
    )
    f = small.reshape(-1, 3).astype(np.float32) / 255.0
    keep = (f.max(1) < 0.98) & (f.mean(1) > 0.02)
    if keep.sum() > 100:
        f = f[keep]
    mean = f.mean(0)
    k = max(0.0, float(mean[1] - mean[2]))
    f[:, 2] = _compensate_red(f[:, 2], f[:, 1], k)
    m = f.mean(0)
    gains = np.clip((m.mean() / np.maximum(m, 1e-4)) ** WB_STRENGTH, 0.5, 3.0) * WARM
    lum = (f * gains) @ _LUMA
    lo, hi = np.percentile(lum, [0.5, 99.5])
    stretch = min(TOP / max(hi - lo, 1e-3), MAX_CONTRAST_GAIN)
    lo = max(lo - (TOP / stretch - (hi - lo)) / 2, 0.0)  # capped: centre the window
    mid = np.clip((np.median(lum) - lo) * stretch, 0.02, 0.98)
    gamma = float(np.clip(np.log(0.45) / np.log(mid), 0.6, 1.0))
    return np.array([k, *gains, lo, stretch, gamma], np.float32)


def _tone(x: np.ndarray, lo: float, scale: float, gamma: float) -> np.ndarray:
    return (np.clip((x - lo) * scale, 0.0, 1.0) ** gamma * 255.0 + 0.5).astype(np.uint8)


def _luts(p: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(blue (256,), green (256,), red (256*256,) indexed red*256 + green)."""
    k, gb, gg, gr, lo, scale, gamma = (float(v) for v in p)
    x = np.arange(256, dtype=np.float32) / 255.0
    red = _compensate_red(x[:, None], x[None, :], k) * gr
    return (
        _tone(x * gb, lo, scale, gamma),
        _tone(x * gg, lo, scale, gamma),
        _tone(red, lo, scale, gamma).reshape(-1),
    )


class ColourCorrector:
    """Per-frame underwater colour correction (see the module docstring).

    Thread-safe: tiles may be corrected from worker threads.
    """

    def __init__(self) -> None:
        self._frames: OrderedDict[object, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self._clahe_clip = 0.0

    @property
    def local_contrast(self) -> float:
        return self._clahe_clip

    def set_local_contrast(self, clip: float) -> None:
        """CLAHE clip limit on what's shown; 0 turns it off."""
        self._clahe_clip = max(0.0, float(clip))

    def remember_frame(self, frame_key: object, full_frame_bgr: np.ndarray) -> None:
        """Measure a full frame once so every tile cropped from it shares its
        correction instead of each crop being measured on its own."""
        if frame_key is None or full_frame_bgr is None or full_frame_bgr.size == 0:
            return
        params = measure_pixels(full_frame_bgr)
        with self._lock:
            self._frames[frame_key] = params
            self._frames.move_to_end(frame_key)
            while len(self._frames) > MAX_REMEMBERED_FRAMES:
                self._frames.popitem(last=False)

    def has_frame(self, frame_key: object) -> bool:
        with self._lock:
            return frame_key in self._frames

    def apply(self, bgr: np.ndarray, frame_key: object = None) -> np.ndarray:
        """Return a colour-corrected copy of *bgr* (BGR uint8)."""
        if bgr is None or bgr.size == 0 or bgr.ndim != 3 or bgr.shape[2] != 3:
            return bgr
        with self._lock:
            params = self._frames.get(frame_key) if frame_key is not None else None
        if params is None:
            params = measure_pixels(bgr)
        lut_b, lut_g, lut_r = _luts(params)
        b, g, r = cv2.split(bgr)
        red = np.take(lut_r, (r.astype(np.intp) << 8) | g)
        out = cv2.merge([cv2.LUT(b, lut_b), cv2.LUT(g, lut_g), red])
        if self._clahe_clip > 0:
            # A CLAHE object isn't safe to share across threads; they're cheap.
            clahe = cv2.createCLAHE(clipLimit=self._clahe_clip, tileGridSize=(8, 8))
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            lab[..., 0] = clahe.apply(lab[..., 0])
            out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = cv2.convertScaleAbs(hsv[..., 1], alpha=SATURATION)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


# -- colour fringes -----------------------------------------------------------

FRINGE_MIN_SIDE_PX = 24  # too small to align
FRINGE_MAX_SHIFT_PX = 12.0
FRINGE_MAX_SHIFT_FRACTION = 1 / 8  # of the crop's short side
FRINGE_ACCEPT_GAIN = 0.02  # keep a shift only if it cuts fringe_energy by >= 2%
CHROMA_MEDIAN_PX = 7
_ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-4)


def _gradients(channel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    channel = cv2.GaussianBlur(channel.astype(np.float32), (0, 0), 0.7)
    return cv2.Sobel(channel, cv2.CV_32F, 1, 0), cv2.Sobel(channel, cv2.CV_32F, 0, 1)


def _gradient_magnitude(channel: np.ndarray) -> np.ndarray:
    m = cv2.magnitude(*_gradients(channel))
    return (m - m.mean()) / (m.std() + 1e-6)


def fringe_energy(bgr: np.ndarray, border: int = 8) -> float:
    """How much red's and blue's edges disagree with green's (lower is better)."""
    inner = (slice(border, -border), slice(border, -border))

    def normalised(channel):
        gx, gy = _gradients(channel)
        spread = cv2.magnitude(gx, gy)[inner].std() + 1e-6
        return gx[inner] / spread, gy[inner] / spread

    b, g, r = (normalised(bgr[:, :, k]) for k in range(3))
    return float(
        np.mean(np.hypot(r[0] - g[0], r[1] - g[1]))
        + np.mean(np.hypot(b[0] - g[0], b[1] - g[1]))
    )


def _shift(channel: np.ndarray, dx: float, dy: float) -> np.ndarray:
    return cv2.warpAffine(
        channel,
        np.float32([[1, 0, -dx], [0, 1, -dy]]),
        channel.shape[::-1],
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )


def _aligned(bgr: np.ndarray) -> np.ndarray:
    limit = min(FRINGE_MAX_SHIFT_PX, FRINGE_MAX_SHIFT_FRACTION * min(bgr.shape[:2]))
    green = _gradient_magnitude(bgr[:, :, 1])
    channels = list(cv2.split(bgr))
    for k in (0, 2):
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            _, warp = cv2.findTransformECC(
                green,
                _gradient_magnitude(bgr[:, :, k]),
                warp,
                cv2.MOTION_TRANSLATION,
                _ECC_CRITERIA,
                None,
                3,
            )
        except cv2.error:  # didn't converge: flat or featureless crop
            continue
        dx, dy = float(warp[0, 2]), float(warp[1, 2])
        if np.hypot(dx, dy) <= limit:
            channels[k] = _shift(channels[k], dx, dy)
    out = cv2.merge(channels)
    if fringe_energy(out) <= fringe_energy(bgr) * (1 - FRINGE_ACCEPT_GAIN):
        return out
    return bgr


def _edge_chroma_median(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    light, a, b = cv2.split(lab)
    weight = cv2.magnitude(*_gradients(light))
    weight = np.clip(weight / (np.percentile(weight, 90) + 1e-6), 0, 1)
    weight = cv2.GaussianBlur(weight, (0, 0), 2)[:, :, None]
    ab = np.dstack([a, b]).astype(np.float32)
    ab_median = np.dstack(
        [cv2.medianBlur(a, CHROMA_MEDIAN_PX), cv2.medianBlur(b, CHROMA_MEDIAN_PX)]
    ).astype(np.float32)
    ab = np.clip(ab * (1 - weight) + ab_median * weight + 0.5, 0, 255).astype(np.uint8)
    return cv2.cvtColor(cv2.merge([light, ab[:, :, 0], ab[:, :, 1]]), cv2.COLOR_LAB2BGR)


def fix_fringes(bgr: np.ndarray) -> np.ndarray:
    """*bgr* with red/blue colour fringes reduced; safe on worker threads."""
    if bgr is None or bgr.ndim != 3 or min(bgr.shape[:2]) < FRINGE_MIN_SIDE_PX:
        return bgr
    return _edge_chroma_median(_aligned(bgr))


# -- brightness / contrast / sharpen -----------------------------------------

SHARPEN_AMOUNT = 1.5


def sharpen(thumb: np.ndarray, enlargement: float) -> np.ndarray:
    """Adaptive unsharp mask on lightness; radius follows *enlargement*."""
    lab = cv2.cvtColor(thumb, cv2.COLOR_BGR2LAB)
    light = lab[:, :, 0].astype(np.float32)
    sigma = max(1.0, 0.8 * enlargement)
    detail = light - cv2.GaussianBlur(light, (0, 0), sigma)
    sample = detail[::3, ::3]
    noise = 1.4826 * float(np.median(np.abs(sample - np.median(sample)))) + 1e-3
    strength = cv2.GaussianBlur(np.abs(detail), (0, 0), sigma)
    weight = np.clip((strength - 1.5 * noise) / (2.0 * noise), 0.0, 1.0)
    lab[:, :, 0] = np.clip(
        light + SHARPEN_AMOUNT * weight * detail + 0.5, 0, 255
    ).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def brightness_contrast(
    bgr: np.ndarray, brightness: int, contrast: float
) -> np.ndarray:
    """Contrast and brightness on lightness only (Lab L, 0-255 units).

    Contrast pivots on the image's own mean lightness, so it spreads light
    and dark apart without making the image as a whole darker or brighter;
    brightness is then added. Colour (a*, b*) is left alone.

    It used to scale each of B, G and R about 128. That stretches the
    differences between channels too, so contrast also raised saturation
    (~40% at 1.5x) and pushed dim, warm areas toward red; channels clipping at
    different levels shifted hue; and with most footage far darker than 128,
    more contrast mainly darkened it (and turned black borders grey).
    """
    if brightness == 0 and contrast == 1.0:
        return bgr
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    light = lab[:, :, 0].astype(np.float32)
    pivot = float(light.mean())
    lab[:, :, 0] = np.clip(
        (light - pivot) * contrast + pivot + brightness + 0.5, 0, 255
    ).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


@dataclass(frozen=True)
class DisplayAdjustment:
    """Everything that changes how tiles are drawn (never what is stored)."""

    colour_correct: bool = False
    local_contrast: float = 0.0  # CLAHE clip; only with colour_correct
    fix_fringes: bool = False
    brightness: int = 0
    contrast: float = 1.0
    sharpen: bool = False

    @property
    def is_neutral(self) -> bool:
        return self == DisplayAdjustment()

    @property
    def needs_source_pixels(self) -> bool:
        """True when the adjustment works on the crop before it's scaled
        (colour / fringes), not just on the scaled thumbnail."""
        return self.colour_correct or self.fix_fringes


def adjust_source(
    bgr: np.ndarray,
    adjustment: DisplayAdjustment,
    corrector: ColourCorrector | None,
    frame_key: object = None,
) -> np.ndarray:
    """Fringes then colour correction, on the unscaled crop or frame."""
    if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3:
        return bgr
    if adjustment.fix_fringes:
        bgr = fix_fringes(bgr)
    if adjustment.colour_correct and corrector is not None:
        bgr = corrector.apply(bgr, frame_key)
    return bgr


def adjust_thumbnail(
    thumb: np.ndarray, adjustment: DisplayAdjustment, enlargement: float
) -> np.ndarray:
    """Sharpen then brightness/contrast, on the scaled thumbnail."""
    if thumb is None or thumb.ndim != 3 or thumb.shape[2] != 3:
        return thumb
    if adjustment.sharpen:
        thumb = sharpen(thumb, enlargement)
    return brightness_contrast(thumb, adjustment.brightness, adjustment.contrast)


__all__ = [
    "ColourCorrector",
    "DisplayAdjustment",
    "adjust_source",
    "adjust_thumbnail",
    "brightness_contrast",
    "fix_fringes",
    "fringe_energy",
    "measure_pixels",
    "sharpen",
]
