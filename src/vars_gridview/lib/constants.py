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
USERNAME_DEFAULT = ""

# Asset paths
ROOT_DIR = Path(__file__).parent.parent
if not ROOT_DIR.exists():  # pyinstaller
    ROOT_DIR = ROOT_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
UI_FILE = ASSETS_DIR / "gridview.ui"
STYLE_DIR = ASSETS_DIR / "style"
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

# GUI settings defaults
GUI_GEOMETRY_DEFAULT = None
GUI_WINDOW_STATE_DEFAULT = None
GUI_SPLITTER1_STATE_DEFAULT = None
GUI_SPLITTER2_STATE_DEFAULT = None
GUI_STYLE_DEFAULT = "default"
GUI_ZOOM_DEFAULT = 0.60

# Settings
SETTINGS = SettingsManager(
    settings=QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        APP_ORGANIZATION,
        application=APP_NAME,
    )
)

SETTINGS.raz_url = ("m3/raz_url", str, RAZIEL_URL_DEFAULT)
SETTINGS.username = ("m3/username", str, USERNAME_DEFAULT)

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
Path(SETTINGS.cache_dir.value).mkdir(parents=True, exist_ok=True)

SETTINGS.embeddings_enabled = (
    "embeddings/enabled",
    bool,
    EMBEDDINGS_ENABLED_DEFAULT,
)

SETTINGS.gui_geometry = ("gui/geometry", QtCore.QByteArray, GUI_GEOMETRY_DEFAULT)
SETTINGS.gui_window_state = (
    "gui/window_state",
    QtCore.QByteArray,
    GUI_WINDOW_STATE_DEFAULT,
)
SETTINGS.gui_splitter1_state = (
    "gui/splitter1_state",
    QtCore.QByteArray,
    GUI_SPLITTER1_STATE_DEFAULT,
)
SETTINGS.gui_splitter2_state = (
    "gui/splitter2_state",
    QtCore.QByteArray,
    GUI_SPLITTER2_STATE_DEFAULT,
)
SETTINGS.gui_style = ("gui/style", str, GUI_STYLE_DEFAULT)
SETTINGS.gui_zoom = ("gui/zoom", float, GUI_ZOOM_DEFAULT)


__all__ = [
    "APP_NAME",
    "APP_ORGANIZATION",
    "APP_VERSION",
    "ROOT_DIR",
    "ASSETS_DIR",
    "ICONS_DIR",
    "UI_FILE",
    "STYLE_DIR",
    "LOG_DIR",
    "SHARKTOPODA_APP_NAME",
    "SETTINGS",
]
