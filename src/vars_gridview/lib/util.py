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


def open_file_browser(path: Path):
    """
    Open a file browser to the given path. Implementation varies by platform.

    Args:
        path: The path to open.
    """
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path] if path.is_file() else ["open", path])
    else:
        subprocess.Popen(["xdg-open", path.parent if path.is_file() else path])
