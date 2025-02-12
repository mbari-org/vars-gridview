from pathlib import Path

from platformdirs import user_cache_dir, user_log_dir

# Application
APP_NAME = "VARS GridView"
APP_ORGANIZATION = "MBARI"

# M3
RAZIEL_URL_DEFAULT = "https://m3.shore.mbari.org/config"

# Asset paths
ROOT_DIR = Path(__file__).parent.parent
if not ROOT_DIR.exists():  # pyinstaller
    ROOT_DIR = ROOT_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
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
