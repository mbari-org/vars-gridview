"""
Application constants.
"""

from pathlib import Path

from PyQt6 import QtCore
from platformdirs import user_cache_dir, user_log_dir

from vars_gridview import __version__
from vars_gridview.lib.settings import SettingsManager


# Application
APP_NAME = "VARS GridView"
APP_ORGANIZATION = "MBARI"
APP_VERSION = __version__

# M3
RAZIEL_URL_DEFAULT = "https://m3.shore.mbari.org/config"

# Asset paths
ROOT_DIR = Path(__file__).parent.parent
if not ROOT_DIR.exists():  # pyinstaller
    ROOT_DIR = ROOT_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
UI_FILE = ASSETS_DIR / "gridview.ui"
STYLE_DIR = ASSETS_DIR / "style"
GUI_SETTINGS_FILE = ASSETS_DIR / "gui.ini"
LOG_DIR = Path(user_log_dir(APP_NAME, APP_ORGANIZATION))

# Appearance defaults
LABEL_FONT_SIZE_DEFAULT = 8
SELECTION_HIGHLIGHT_COLOR_DEFAULT = "#34a1eb"

# Video player defaults
SHARKTOPODA_HOST_DEFAULT = "::1"
SHARKTOPODA_OUTGOING_PORT_DEFAULT = 8800
SHARKTOPODA_INCOMING_PORT_DEFAULT = 8801

# Data cache
CACHE_DIR_DEFAULT = Path(user_cache_dir(APP_NAME))

# Sharktopoda
SHARKTOPODA_APP_NAME = "Sharktopoda"

# Embeddings
EMBEDDINGS_ENABLED_DEFAULT = False

# Settings
SETTINGS = SettingsManager.get_instance()

SETTINGS.raz_url = ("m3/raz_url", str, RAZIEL_URL_DEFAULT)

SETTINGS.label_font_size = (
    "appearance/label_font_size",
    int,
    LABEL_FONT_SIZE_DEFAULT,
)
SETTINGS.selection_highlight_color = (
    "appearance/selection_highlight_color",
    str,
    SELECTION_HIGHLIGHT_COLOR_DEFAULT,
)

SETTINGS.sharktopoda_host = (
    "video/sharktopoda_host",
    str,
    SHARKTOPODA_HOST_DEFAULT,
)
SETTINGS.sharktopoda_outgoing_port = (
    "video/sharktopoda_outgoing_port",
    int,
    SHARKTOPODA_OUTGOING_PORT_DEFAULT,
)
SETTINGS.sharktopoda_incoming_port = (
    "video/sharktopoda_incoming_port",
    int,
    SHARKTOPODA_INCOMING_PORT_DEFAULT,
)
SETTINGS.sharktopoda_autoconnect = (
    "video/sharktopoda_autoconnect",
    bool,
    True,
)

SETTINGS.cache_dir = (
    "cache/dir",
    str,
    str(CACHE_DIR_DEFAULT),
)
SETTINGS.cache_size_mb = (
    "cache/size_mb",
    int,
    1000,
)

SETTINGS.embeddings_enabled = (
    "embeddings/enabled",
    bool,
    EMBEDDINGS_ENABLED_DEFAULT,
)


__all__ = [
    "APP_NAME",
    "APP_ORGANIZATION",
    "APP_VERSION",
    "RAZIEL_URL_DEFAULT",
    "ROOT_DIR",
    "ASSETS_DIR",
    "ICONS_DIR",
    "UI_FILE",
    "STYLE_DIR",
    "GUI_SETTINGS_FILE",
    "LOG_DIR",
    "LABEL_FONT_SIZE_DEFAULT",
    "SELECTION_HIGHLIGHT_COLOR_DEFAULT",
    "SHARKTOPODA_HOST_DEFAULT",
    "SHARKTOPODA_OUTGOING_PORT_DEFAULT",
    "SHARKTOPODA_INCOMING_PORT_DEFAULT",
    "CACHE_DIR_DEFAULT",
    "SHARKTOPODA_APP_NAME",
    "EMBEDDINGS_ENABLED_DEFAULT",
    "SETTINGS",
]
GUI_SETTINGS = QtCore.QSettings(
    str(GUI_SETTINGS_FILE), QtCore.QSettings.Format.IniFormat
)
