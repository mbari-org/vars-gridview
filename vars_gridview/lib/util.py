"""
Utilities.
"""


import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


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


def parse_iso(timestamp: str) -> datetime:
    """
    Parse an ISO timestamp.

    Args:
        timestamp: The timestamp to parse.

    Returns:
        The parsed timestamp.
    """
    if isinstance(timestamp, datetime):  # short circuit
        return timestamp

    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")


def parse_sqlserver_native(timestamp: str) -> datetime:
    """
    Parse a SQL Server native timestamp.

    Args:
        timestamp: The timestamp to parse.

    Returns:
        The parsed timestamp.
    """
    if isinstance(timestamp, datetime):  # short circuit
        return timestamp

    datetime_part, *decimal_part = timestamp.split(".")
    decimal_part = decimal_part[0] if decimal_part else None
    if "+" in decimal_part:
        decimal_part, _ = decimal_part.split("+")
    subsecond_timedelta = (
        timedelta(seconds=float(f".{decimal_part}")) if decimal_part else timedelta()
    )
    return datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S") + subsecond_timedelta


def open_file_browser(path: Path):
    """
    Open a file browser to the given path. Implementation varies by platform.

    Args:
        path: The path to open.
    """
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open" "-R", path] if path.is_file() else ["open", path])
    else:
        subprocess.Popen(["xdg-open", path.parent if path.is_file() else path])
