from pathlib import Path

from platformdirs import user_cache_dir, user_log_dir

# Application
APP_NAME = "VARS GridView"
APP_ORGANIZATION = "MBARI"

# SQL
SQL_URL_DEFAULT = "perseus.shore.mbari.org"
SQL_USER_DEFAULT = "everyone"
SQL_PASSWORD_DEFAULT = "guest"
SQL_DATABASE_DEFAULT = "M3_ANNOTATIONS"

# M3
RAZIEL_URL_DEFAULT = "http://m3.shore.mbari.org/config"

# Asset paths
ROOT_DIR = Path(__file__).parent.parent
if not ROOT_DIR.exists():  # pyinstaller
    ROOT_DIR = ROOT_DIR.parent
ASSETS_DIR = ROOT_DIR / "assets"
UI_FILE = ASSETS_DIR / "gridview.ui"
STYLE_DIR = ASSETS_DIR / "style"
GUI_SETTINGS_FILE = ASSETS_DIR / "gui.ini"
BASE_QUERY_FILE = ASSETS_DIR / "base_query.sql"
LOG_DIR = Path(user_log_dir(APP_NAME, APP_ORGANIZATION))

# Preferred image type
IMAGE_TYPE = "image/png"

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