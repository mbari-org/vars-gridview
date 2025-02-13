"""
Utilities.
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import shlex
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np
from cachetools import cached, LRUCache
import requests

from vars_gridview.lib.m3 import BEHOLDER_CLIENT

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
    path_str = shlex.quote(str(path))
    if sys.platform == "win32":
        process = subprocess.Popen(f"explorer /select,{path_str}")
    elif sys.platform == "darwin":
        process = subprocess.Popen(
            ["open", "-R", path_str] if path.is_file() else ["open", path_str]
        )
    else:
        process = subprocess.Popen(
            ["xdg-open", path.parent if path.is_file() else path_str]
        )
    return process


def parse_tsv(data: str) -> tuple[list[str], list[list[str]]]:
    """
    Parse a TSV string into a header and rows.

    Args:
        data (str): TSV data.

    Returns:
        tuple[list[str], list[list[str]]]: Header and rows.
    """
    lines = data.split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, rows


@cached(image_cache)
def fetch_image(url: str) -> np.ndarray:
    """
    Fetch an image from the given URL.

    Args:
        url (str): The URL to fetch the image from.

    Returns:
        np.ndarray: The image as a NumPy array.
    """
    parsed_url = urlparse(url)

    image_bytes = None
    if parsed_url.scheme in ("http", "https"):
        response = requests.get(url)
        response.raise_for_status()
        image_bytes = response.content
    elif parsed_url.scheme == "beholder":
        video_url = (
            f"https://{parsed_url.netloc}{parsed_url.path}"  # TODO: This is brittle
        )
        query = parse_qs(parsed_url.query)
        query_ms = query.get("ms", None)
        if not query_ms:
            raise ValueError("Timestamp not provided in the query string.")
        try:
            timestamp_ms = int(query_ms[0])
        except ValueError as e:
            raise ValueError("Invalid timestamp provided in the query string.") from e
        image_bytes = BEHOLDER_CLIENT.capture_raw(video_url, timestamp_ms)
    else:
        raise ValueError(f"Unsupported image URL scheme: {parsed_url.scheme}")

    return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
