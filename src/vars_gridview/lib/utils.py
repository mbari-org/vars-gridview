"""General-purpose utilities for VARS GridView.

This module contains pure functions and lightweight helpers used across the
application.  It deliberately has minimal dependencies so it can be imported
without a running ``QApplication``.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import requests
from cachetools import LRUCache, cached
from PyQt6.QtGui import QColor

from vars_gridview.lib.log import LOGGER


# Module-level LRU cache shared by fetch_image.
_image_cache: LRUCache = LRUCache(maxsize=128)


def get_timestamp(
    video_start_timestamp: datetime,
    recorded_timestamp: Optional[datetime] = None,
    elapsed_time_millis: Optional[int] = None,
    timecode: Optional[str] = None,
) -> Optional[datetime]:
    """Resolve the best available timestamp for an annotation.

    Resolution order (highest to lowest precision):

    1. *recorded_timestamp* — microsecond precision.
    2. *elapsed_time_millis* — millisecond precision.
    3. *timecode* (``HH:MM:SS:ff``) — second precision.

    Args:
        video_start_timestamp: UTC start time of the containing video.
        recorded_timestamp: Pre-computed absolute timestamp, if available.
        elapsed_time_millis: Elapsed milliseconds from video start.
        timecode: SMPTE timecode string (``"HH:MM:SS:FF"``).

    Returns:
        The resolved :class:`~datetime.datetime`, or ``None`` if none of the
        optional inputs were provided.
    """
    if recorded_timestamp is not None:
        return recorded_timestamp
    if elapsed_time_millis is not None:
        return video_start_timestamp + timedelta(milliseconds=int(elapsed_time_millis))
    if timecode is not None:
        hours, minutes, seconds, _ = map(int, timecode.split(":"))
        return video_start_timestamp + timedelta(
            hours=hours, minutes=minutes, seconds=seconds
        )
    return None


def open_file_browser(path: Path) -> subprocess.Popen:
    """Open the system file manager and reveal *path*.

    Uses ``explorer`` on Windows, ``open -R`` on macOS, and ``xdg-open`` on
    Linux/other systems.

    Args:
        path: File or directory to reveal.

    Returns:
        The :class:`~subprocess.Popen` handle for the launched process.

    Raises:
        FileNotFoundError: If *path* does not exist on disk.
    """
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    path_str = str(path)
    if sys.platform == "win32":
        return subprocess.Popen(f"explorer /select,{path_str}")
    if sys.platform == "darwin":
        return subprocess.Popen(
            ["open", "-R", path_str] if path.is_file() else ["open", path_str]
        )
    # Linux / other Unix
    return subprocess.Popen(
        ["xdg-open", str(path.parent) if path.is_file() else path_str]
    )


def parse_tsv(data: str) -> tuple[list[str], list[list[str]]]:
    """Parse a tab-separated-values string into a header and data rows.

    Args:
        data: Complete TSV text (header on line 0, rows on subsequent lines).

    Returns:
        A ``(header, rows)`` tuple where *header* is a list of column names and
        *rows* is a list of string lists, one per non-empty data line.
    """
    lines = data.split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, rows


@cached(_image_cache)
def fetch_image(url: str, elapsed_time_millis: Optional[int] = None) -> np.ndarray:
    """Fetch and decode a frame image, with LRU caching.

    When *elapsed_time_millis* is ``None``, the image is fetched directly from
    *url* via HTTP GET.  When provided, the Beholder client is used to capture
    the video frame at that offset.

    Args:
        url: Image URL or video-reference URL.
        elapsed_time_millis: Optional elapsed-time offset for video frames.

    Returns:
        BGR image as an ``(H, W, 3)`` uint8 NumPy array (OpenCV convention).

    Raises:
        requests.HTTPError: On any network error.
    """
    try:
        if elapsed_time_millis is None:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_bytes: bytes = response.content
        else:
            from vars_gridview.lib.m3 import BEHOLDER_CLIENT  # lazy to avoid circulars

            image_bytes = BEHOLDER_CLIENT.capture_raw(url, elapsed_time_millis)
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
    """Return a stable HSL colour derived from the concept name.

    The hue is computed from the sum of ordinal values of the concept's
    characters, providing a deterministic but visually spread-out palette.

    Args:
        concept: Scientific or common name to colourise.

    Returns:
        A light-pastel :class:`~PyQt6.QtGui.QColor` unique to *concept*.
    """
    hue_raw = sum(ord(c) for c in concept) << 5
    color = QColor()
    color.setHsl(round((hue_raw % 360) / 360 * 255), 255, 217, 255)
    return color


__all__ = [
    "get_timestamp",
    "open_file_browser",
    "parse_tsv",
    "fetch_image",
    "color_for_concept",
]
