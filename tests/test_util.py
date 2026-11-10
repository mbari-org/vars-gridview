import unittest
from datetime import datetime, timedelta, timezone

from vars_gridview.lib.common.time import get_timestamp


class TestUtils(unittest.TestCase):
    def test_get_timestamp_with_recorded_timestamp(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        recorded_timestamp = datetime(2023, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        result = get_timestamp(
            video_start_timestamp, recorded_timestamp=recorded_timestamp
        )
        self.assertEqual(result, recorded_timestamp)

    def test_get_timestamp_with_elapsed_time_millis(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        elapsed_time_millis = 3600000  # 1 hour
        result = get_timestamp(
            video_start_timestamp, elapsed_time_millis=elapsed_time_millis
        )
        expected_timestamp = video_start_timestamp + timedelta(
            milliseconds=elapsed_time_millis
        )
        self.assertEqual(result, expected_timestamp)

    def test_get_timestamp_with_timecode(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        timecode = "01:00:00:00"  # 1 hour
        result = get_timestamp(video_start_timestamp, timecode=timecode)
        expected_timestamp = video_start_timestamp + timedelta(hours=1)
        self.assertEqual(result, expected_timestamp)


if __name__ == "__main__":
    unittest.main()
