"""Time and timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timedelta


def get_timestamp(
    video_start_timestamp: datetime,
    recorded_timestamp: datetime | None = None,
    elapsed_time_millis: int | None = None,
    timecode: str | None = None,
) -> datetime | None:
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
