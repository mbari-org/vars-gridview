from pathlib import Path
from typing import Optional

from PyQt6 import QtCore
from diskcache import Cache

from vars_gridview.lib.constants import SETTINGS


class CacheController(QtCore.QObject):
    """
    Cache controller. Manages the image cache.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.recreate_cache()
        SETTINGS.cache_dir.valueChanged.connect(self.recreate_cache)
        SETTINGS.cache_size_mb.valueChanged.connect(self.recreate_cache)

    @QtCore.pyqtSlot()
    def recreate_cache(self):
        """
        Recreate the cache from the current settings.
        """
        cache_dir = Path(SETTINGS.cache_dir.value) / "images"
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_size_mb = SETTINGS.cache_size_mb.value

        self._cache = Cache(str(cache_dir), size_limit=cache_size_mb * 1024 * 1024)

    def insert(self, key: str, data: bytes):
        """
        Save a file to the cache.

        Args:
            key: The key.
            data: The file data.
        """
        self._cache.set(key, data)

    def get(self, key: str) -> Optional[bytes]:
        """
        Get the data for a key.

        Args:
            key: The key.

        Returns:
            The data, or None if the key is not in the cache or the file could not be read.
        """
        return self._cache.get(key)

    def remove(self, key: str):
        """
        Remove a key from the cache.

        Args:
            key (str): The key.
        """
        self._cache.delete(key)

    def clear(self):
        """
        Clear the cache.

        WARNING: This will delete all files in the cache data directory.
        """
        self._cache.clear()
