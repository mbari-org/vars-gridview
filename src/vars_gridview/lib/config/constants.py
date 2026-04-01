"""Application-wide constants.

This module defines pure constants (no side-effects, no settings, no Qt
session objects).  The global ``SETTINGS`` singleton is created lazily by
:func:`get_settings` so that this module is safe to import in unit tests
without a running ``QApplication``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING
from platformdirs import user_log_dir

from vars_gridview import __version__

if TYPE_CHECKING:
    from vars_gridview.lib.config.settings import AppSettings

# ── Application identity ───────────────────────────────────────────────────────
APP_NAME: str = "VARS GridView"
APP_ORGANIZATION: str = "MBARI"
APP_VERSION: str = __version__

# ── Asset paths ────────────────────────────────────────────────────────────────
# constants.py lives under ``lib/config``; package root is three levels up.
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
if not ROOT_DIR.exists():  # PyInstaller frozen bundle fallback
    ROOT_DIR = ROOT_DIR.parent

ASSETS_DIR: Path = ROOT_DIR / "assets"
ICONS_DIR: Path = ASSETS_DIR / "icons"
STYLE_DIR: Path = ASSETS_DIR / "style"
UI_FILE: Path = ASSETS_DIR / "gridview.ui"
LOG_DIR: Path = Path(user_log_dir(APP_NAME, APP_ORGANIZATION))

# ── Lazily-initialised global settings singleton ───────────────────────────────
_SETTINGS: Optional[AppSettings] = None  # type: ignore[name-defined]

SHARKTOPODA_APP_NAME: str = "Sharktopoda"


def get_settings() -> AppSettings:  # type: ignore[name-defined]
    """Return the global :class:`AppSettings` singleton, constructing it once.

    Returns:
        The application-wide :class:`~vars_gridview.lib.config.settings.AppSettings`.
    """
    global _SETTINGS
    if _SETTINGS is None:
        from vars_gridview.lib.config.settings import build_settings

        _SETTINGS = build_settings()
    return _SETTINGS


# Convenience alias kept for backward-compatibility with code that imports SETTINGS
# directly.  New code should call get_settings() instead.
class _SettingsProxy:
    """Forwards attribute access to the lazily-created AppSettings singleton."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __setattr__(self, name: str, value) -> None:
        setattr(get_settings(), name, value)


SETTINGS = _SettingsProxy()

__all__ = [
    "APP_NAME",
    "APP_ORGANIZATION",
    "APP_VERSION",
    "ASSETS_DIR",
    "ICONS_DIR",
    "STYLE_DIR",
    "UI_FILE",
    "LOG_DIR",
    "ROOT_DIR",
    "SHARKTOPODA_APP_NAME",
    "SETTINGS",
    "get_settings",
]
