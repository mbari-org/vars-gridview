"""Filesystem and shell integration helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def open_file_browser(path: Path) -> subprocess.Popen:
    """Open the system file manager and reveal *path*."""
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    path_str = str(path)
    if sys.platform == "win32":
        return subprocess.Popen(f"explorer /select,{path_str}")
    if sys.platform == "darwin":
        return subprocess.Popen(
            ["open", "-R", path_str] if path.is_file() else ["open", path_str]
        )
    return subprocess.Popen(
        ["xdg-open", str(path.parent) if path.is_file() else path_str]
    )


__all__ = ["open_file_browser"]
