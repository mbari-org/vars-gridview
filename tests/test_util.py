import unittest
from datetime import datetime, timedelta
from pathlib import Path
from vars_gridview.lib.utils import get_timestamp, open_file_browser
import time


class TestUtils(unittest.TestCase):
    def test_get_timestamp_with_recorded_timestamp(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0)
        recorded_timestamp = datetime(2023, 1, 1, 1, 0, 0)
        result = get_timestamp(
            video_start_timestamp, recorded_timestamp=recorded_timestamp
        )
        self.assertEqual(result, recorded_timestamp)

    def test_get_timestamp_with_elapsed_time_millis(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0)
        elapsed_time_millis = 3600000  # 1 hour
        result = get_timestamp(
            video_start_timestamp, elapsed_time_millis=elapsed_time_millis
        )
        expected_timestamp = video_start_timestamp + timedelta(
            milliseconds=elapsed_time_millis
        )
        self.assertEqual(result, expected_timestamp)

    def test_get_timestamp_with_timecode(self):
        video_start_timestamp = datetime(2023, 1, 1, 0, 0, 0)
        timecode = "01:00:00:00"  # 1 hour
        result = get_timestamp(video_start_timestamp, timecode=timecode)
        expected_timestamp = video_start_timestamp + timedelta(hours=1)
        self.assertEqual(result, expected_timestamp)

    def test_open_file_browser(self):
        path = Path("/tmp")
        process = open_file_browser(path)
        try:
            time.sleep(1)  # Give the process some time to complete
            process.terminate()  # Terminate the process
            process.wait()  # Wait for the process to terminate
        except Exception as e:
            self.fail(f"Process termination failed: {e}")


if __name__ == "__main__":
    unittest.main()
