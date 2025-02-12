"""
Singleton class for logging.
"""

import logging
from datetime import datetime

from vars_gridview.lib.constants import LOG_DIR


class AppLogger:
    """
    Singleton application logger. Use get_instance() to get the instance.
    """

    @staticmethod
    def get_instance() -> "AppLogger":
        """
        Get the singleton instance.
        """
        if not hasattr(AppLogger, "_instance"):
            AppLogger._instance = AppLogger()
        return AppLogger._instance

    def __init__(self):
        if hasattr(AppLogger, "_instance"):
            raise Exception("This class is a singleton! Use get_instance() instead.")

        # Create logger
        self._logger = logging.getLogger("vars-gridview")
        self._logger.setLevel(logging.DEBUG)

        # Create formatter
        self._formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create stream handler
        self._stream_handler = logging.StreamHandler()
        self._stream_handler.setLevel(logging.WARN)
        self._stream_handler.setFormatter(self._formatter)

        # Create file handler
        self._file_handler = logging.FileHandler(
            str(LOG_DIR / (datetime.now().strftime("%Y-%m-%d") + ".txt"))
        )
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(self._formatter)

        # Add handlers
        self._logger.addHandler(self._stream_handler)
        self._logger.addHandler(self._file_handler)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def set_stream_level(self, level) -> None:
        """
        Set the stream handler level.

        Args:
            level: The level to set.
        """
        self._stream_handler.setLevel(level)

    def set_file_level(self, level) -> None:
        """
        Set the file handler level.

        Args:
            level: The level to set.
        """
        self._file_handler.setLevel(level)


# Create a logs dir if it does not exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = AppLogger.get_instance().logger
