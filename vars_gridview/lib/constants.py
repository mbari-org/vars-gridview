from pathlib import Path

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
ASSETS_DIR = ROOT_DIR / "assets"
UI_FILE = ASSETS_DIR / "gridview.ui"
STYLE_DIR = ASSETS_DIR / "style"
GUI_SETTINGS_FILE = ASSETS_DIR / "gui.ini"
BASE_QUERY_FILE = ASSETS_DIR / "base_query.sql"
LOG_DIR = ROOT_DIR / "logs"

# Preferred image type
IMAGE_TYPE = "image/png"