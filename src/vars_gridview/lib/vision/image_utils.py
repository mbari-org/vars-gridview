"""Image fetch/decode and concept-colour helpers."""

from __future__ import annotations

from functools import cache
from typing import Optional

import cv2
import numpy as np
import requests
from beholder_client import BeholderClient
from PyQt6.QtGui import QColor

from vars_gridview.lib.runtime.log import LOGGER


def fetch_image(
    url: str,
    elapsed_time_millis: Optional[int] = None,
    beholder_client: Optional[BeholderClient] = None,
) -> np.ndarray:
    """Fetch and decode a still image or Beholder frame."""
    try:
        if elapsed_time_millis is None:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_bytes: bytes = response.content
        else:
            if beholder_client is None:
                raise ValueError(
                    "beholder_client is required when elapsed_time_millis is provided"
                )
            image_bytes = beholder_client.capture_raw(url, elapsed_time_millis)
    except requests.HTTPError as exc:
        ms_suffix = (
            f" at {elapsed_time_millis} ms" if elapsed_time_millis is not None else ""
        )
        LOGGER.error(f"Failed to fetch image from {url}{ms_suffix}: {exc}")
        if exc.response is not None:
            LOGGER.debug(
                f"HTTP {exc.response.status_code} headers: "
                + ", ".join(f"{k}: {v}" for k, v in exc.response.headers.items())
            )
        raise

    return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)


@cache
def color_for_concept(concept: str) -> QColor:
    """Return a stable HSL colour derived from the concept name."""
    hue_raw = sum(ord(c) for c in concept) << 5
    color = QColor()
    color.setHsl(round((hue_raw % 360) / 360 * 255), 255, 217, 255)
    return color


__all__ = ["fetch_image", "color_for_concept"]
