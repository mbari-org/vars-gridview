"""Application logging singleton."""

import logging
from datetime import datetime
from pathlib import Path


class AppLogger:
    """Singleton logger for the VARS GridView application.

    Writes DEBUG+ to a daily rotating log file and WARN+ to the console.
    Use ``get_instance()`` to retrieve the single shared instance.

    Example:
        >>> logger = AppLogger.get_instance().logger
        >>> logger.info("Application started")
    """

    _instance: "AppLogger | None" = None

    @staticmethod
    def get_instance() -> "AppLogger":
        """Return the singleton ``AppLogger`` instance, creating it if needed."""
        if AppLogger._instance is None:
            AppLogger._instance = AppLogger()
        return AppLogger._instance

    def __init__(self) -> None:
        """Initialise handlers and attach them to the ``vars-gridview`` logger.

        Raises:
            RuntimeError: If called more than once (use ``get_instance()``).
        """
        if AppLogger._instance is not None:
            raise RuntimeError("AppLogger is a singleton - use get_instance().")

        # Determine the platform log directory lazily to avoid circular imports.
        from platformdirs import user_log_dir

        log_dir = Path(user_log_dir("VARS GridView", "MBARI"))
        log_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("vars-gridview")
        self._logger.setLevel(logging.DEBUG)

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        # Stream handler - warnings and above only
        self._stream_handler = logging.StreamHandler()
        self._stream_handler.setLevel(logging.WARNING)
        self._stream_handler.setFormatter(fmt)

        # File handler - everything (DEBUG+)
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.txt"
        self._file_handler = logging.FileHandler(str(log_file))
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(fmt)

        self._logger.addHandler(self._stream_handler)
        self._logger.addHandler(self._file_handler)

    @property
    def logger(self) -> logging.Logger:
        """The underlying :class:`logging.Logger` instance."""
        return self._logger

    def set_stream_level(self, level: int) -> None:
        """Set the severity level for the console (stream) handler.

        Args:
            level: A :mod:`logging` level constant such as ``logging.DEBUG``.
        """
        self._stream_handler.setLevel(level)

    def set_file_level(self, level: int) -> None:
        """Set the severity level for the file handler.

        Args:
            level: A :mod:`logging` level constant such as ``logging.DEBUG``.
        """
        self._file_handler.setLevel(level)


#: Module-level logger shortcut.  Re-exported for convenience.
LOGGER: logging.Logger = AppLogger.get_instance().logger

__all__ = ["AppLogger", "LOGGER"]
