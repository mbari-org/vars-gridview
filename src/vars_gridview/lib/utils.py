"""
Utilities.
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import requests
from PyQt6.QtGui import QColor
from cachetools import cached, LRUCache
from functools import cache

from vars_gridview.lib.log import LOGGER


image_cache = LRUCache(maxsize=128)


def get_timestamp(
    video_start_timestamp: datetime,
    recorded_timestamp: Optional[datetime] = None,
    elapsed_time_millis: Optional[int] = None,
    timecode: Optional[str] = None,
) -> Optional[datetime]:
    """
    Get a timestamp from the given parameters. One of the following must be provided:
    - recorded_timestamp
    - elapsed_time_millis
    - timecode
    or else None will be returned.

    Args:
        video_start_timestamp: The video's start timestamp.
        recorded_timestamp: The recorded timestamp.
        elapsed_time_millis: The elapsed time in milliseconds.
        timecode: The timecode.

    Returns:
        The timestamp, or None if none could be determined.
    """
    # First, try to use the recorded timestamp (microsecond resolution)
    if recorded_timestamp is not None:
        return recorded_timestamp

    # Next, try to use the elapsed time in milliseconds (millisecond resolution)
    elif elapsed_time_millis is not None:
        return video_start_timestamp + timedelta(milliseconds=int(elapsed_time_millis))

    # Last, try to use the timecode (second resolution)
    elif timecode is not None:
        hours, minutes, seconds, _ = map(int, timecode.split(":"))
        return video_start_timestamp + timedelta(
            hours=hours, minutes=minutes, seconds=seconds
        )

    # If none of the above worked, return None
    return None


def open_file_browser(path: Path) -> subprocess.Popen:
    """
    Open a file browser to the given path. Implementation varies by platform.

    Args:
        path: The path to open.

    Returns:
        The Popen object of the opened process.
    """
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    path_str = str(path)
    if sys.platform == "win32":
        process = subprocess.Popen(f"explorer /select,{path_str}")
    elif sys.platform == "darwin":
        process = subprocess.Popen(
            ["open", "-R", path_str] if path.is_file() else ["open", path_str]
        )
    else:
        process = subprocess.Popen(
            ["xdg-open", str(path.parent) if path.is_file() else path_str]
        )
    return process


def parse_tsv(data: str) -> Tuple[List[str], List[List[str]]]:
    """
    Parse a TSV string into a header and rows.

    Args:
        data (str): TSV data.

    Returns:
        Tuple[List[str], List[List[str]]]: Header and rows.
    """
    lines = data.split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, rows


@cached(image_cache)
def fetch_image(url: str, elapsed_time_millis: Optional[int] = None) -> np.ndarray:
    """
    Fetch an image from the given URL.

    Args:
        url (str): The URL to fetch the image from.
        elapsed_time_millis (int, optional): The elapsed time in milliseconds.

    Returns:
        np.ndarray: The image as a NumPy array.

    Raises:
        requests.HTTPError: If the request fails.
    """
    image_bytes = None
    try:
        if elapsed_time_millis is None:
            response = requests.get(url)
            response.raise_for_status()
            image_bytes = response.content
        else:
            from vars_gridview.lib.m3 import BEHOLDER_CLIENT

            image_bytes = BEHOLDER_CLIENT.capture_raw(url, elapsed_time_millis)
    except requests.HTTPError as e:
        ms_str = (
            f" at {elapsed_time_millis} ms" if elapsed_time_millis is not None else ""
        )
        LOGGER.error(f"Failed to fetch image from {url}{ms_str}: {e}")
        LOGGER.debug(
            f"Error response with status {e.response.status_code}:\nHeaders:\n{'\n'.join(['- ' + hk + ': ' + hv for hk, hv in e.response.headers.items()])}\n{e.response.content}"
        )
        raise e

    return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)


@cache
def color_for_concept(concept: str) -> QColor:
    """
    Get a color for the given concept.

    Args:
        concept (str): The concept.

    Returns:
        QColor: The color.
    """
    hash = sum(map(ord, concept)) << 5
    color = QColor()
    color.setHsl(round((hash % 360) / 360 * 255), 255, 217, 255)
    return color
