"""Time and timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def get_timestamp(
    video_start_timestamp: datetime,
    recorded_timestamp: Optional[datetime] = None,
    elapsed_time_millis: Optional[int] = None,
    timecode: Optional[str] = None,
) -> Optional[datetime]:
    """Resolve the best available timestamp for an annotation."""
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


__all__ = ["get_timestamp"]
