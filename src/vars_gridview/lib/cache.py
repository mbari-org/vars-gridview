import json
from pathlib import Path
from shutil import rmtree
from typing import Iterable, Optional
from uuid import uuid4
from collections import OrderedDict

from PyQt6 import QtCore

from vars_gridview.lib.constants import SETTINGS


class CacheController(QtCore.QObject):
    """
    Cache controller. Manages the image cache.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._manifest = self._load_manifest()

    @property
    def cache_dir(self) -> Path:
        """
        Get the cache directory.

        Returns:
            The cache directory.
        """
        cache_dir = Path(SETTINGS.cache_dir.value)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @property
    def cache_size_mb(self) -> int:
        """
        Get the cache size in MB.

        Returns:
            The cache size in MB.
        """
        return SETTINGS.cache_size_mb.value

    @property
    def data_dir(self) -> Path:
        """
        Get the data directory.

        Returns:
            The data directory.
        """
        data_dir = self.cache_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @property
    def manifest_path(self) -> Path:
        """
        Get the manifest path.

        Returns:
            The manifest path.
        """
        return self.cache_dir / "manifest.json"

    def _load_manifest(self) -> OrderedDict:
        """
        Load the manifest.

        Returns:
            The manifest.
        """
        if self.manifest_path.exists():
            with open(self.manifest_path, "r") as f:
                return OrderedDict(json.load(f))
        return OrderedDict()

    def _save_manifest(self, manifest: OrderedDict):
        """
        Save the manifest.

        Args:
            manifest: The manifest.
        """
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    def _current_timestamp(self) -> int:
        """
        Get the current timestamp.

        Returns:
            The current timestamp.
        """
        return QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()

    @property
    def cache_data_paths(self) -> Iterable[Path]:
        """
        Get the cache data paths.

        Returns:
            The cache data paths.
        """
        return (self.data_dir / entry["name"] for entry in self._manifest.values())

    @property
    def cache_size(self) -> int:
        """
        Get the cache size in bytes.

        Returns:
            The cache size in bytes.
        """
        return sum(path.stat().st_size for path in self.cache_data_paths)

    @property
    def lru_key(self) -> Optional[str]:
        """
        Get the least recently used key.

        Returns:
            The least recently used key, or None if the cache is empty.
        """
        if len(self._manifest) == 0:
            return None

        return next(iter(self._manifest))

    def _balance_cache(self):
        """
        Balance the cache.

        If the cache size exceeds the maximum size, delete the oldest files until the cache size is below the maximum.
        """
        max_cache_size = self.cache_size_mb * 1024 * 1024
        while self.cache_size > max_cache_size:
            lru_key = self.lru_key
            if lru_key is None:
                break

            print(f"Removing LRU key: {lru_key}")  # Debug statement
            self.remove(lru_key)

    def insert(self, key: str, data: bytes):
        """
        Save a file to the cache.

        Args:
            key: The key.
            data: The file data.
        """
        # Get a unique filename
        output_path = self.data_dir / f"{uuid4().hex.lower()}"
        while output_path.exists():
            output_path = self.data_dir / f"{uuid4().hex.lower()}"

        # Write the file
        try:
            with open(output_path, "wb") as out:
                out.write(data)
        except FileNotFoundError as e:
            print(f"Failed to write file to cache: {e}")
            return

        # Update the cache manifest
        self._manifest[key] = {
            "name": str(output_path.relative_to(self.data_dir)),
            "timestamp": self._current_timestamp(),
        }

        # Balance the cache
        self._balance_cache()

        self._save_manifest(self._manifest)

    def get(self, key: str) -> Optional[bytes]:
        """
        Get the data for a key.

        Args:
            key: The key.

        Returns:
            The data, or None if the key is not in the cache or the file could not be read.
        """
        # Get the manifest entry
        entry = self._manifest.get(key, None)
        if entry is None:  # Key not in cache
            return None

        # Update the manifest
        entry["timestamp"] = self._current_timestamp()
        self._save_manifest(self._manifest)

        # Read the file
        try:
            with open(self.data_dir / entry["name"], "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def remove(self, key: str):
        """
        Remove a key from the cache.

        Args:
            key: The key.
        """
        # Get the manifest entry
        entry = self._manifest.get(key, None)
        if entry is None:  # Key not in cache
            return

        # Delete the file
        path = self.data_dir / entry["name"]
        try:
            path.unlink()
        except FileNotFoundError:
            pass

        # Update the manifest
        del self._manifest[key]
        self._save_manifest(self._manifest)

    def clear(self):
        """
        Clear the cache.

        WARNING: This will delete all files in the cache data directory.
        """
        rmtree(self.data_dir, ignore_errors=True)

        self._manifest = OrderedDict()
        self._save_manifest(self._manifest)

    def current_cache_usage(self) -> int:
        """
        Get the current cache usage in bytes.

        Returns:
            The current cache usage in bytes.
        """
        return self.cache_size
