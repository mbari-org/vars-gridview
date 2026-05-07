"""Install and uninstall Linux desktop entry assets for VARS GridView."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from vars_gridview.lib.config.constants import APP_NAME, ICONS_DIR


APP_ID = "vars-gridview"
APP_COMMENT = "Review and correct VARS localizations in bulk"
ICONSET_DIR = ICONS_DIR / "VARSGridView.iconset"
ICON_SIZES = (16, 32, 128, 256, 512)


def _xdg_data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME", "").strip()
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "share"


def _desktop_file_path() -> Path:
    return _xdg_data_home() / "applications" / f"{APP_ID}.desktop"


def _icons_root() -> Path:
    return _xdg_data_home() / "icons" / "hicolor"


def _icon_target_path(size: int) -> Path:
    return _icons_root() / f"{size}x{size}" / "apps" / f"{APP_ID}.png"


def _resolve_exec_path() -> str:
    executable = shutil.which(APP_ID)
    if executable:
        return str(Path(executable).resolve())

    argv0 = Path(sys.argv[0])
    if argv0.exists():
        return str(argv0.resolve())

    return APP_ID


def _desktop_entry_text(exec_path: str) -> str:
    return "\n".join(
        [
            "[Desktop Entry]",
            "Version=1.0",
            "Type=Application",
            f"Name={APP_NAME}",
            f"Comment={APP_COMMENT}",
            f"Exec={exec_path}",
            f"Icon={APP_ID}",
            "Terminal=false",
            "Categories=Science;Graphics;Education;",
            "StartupNotify=true",
            f"StartupWMClass={APP_NAME}",
            "",
        ]
    )


def _best_effort_run(command: list[str]) -> None:
    try:
        subprocess.run(
            command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError:
        return


def install_desktop_entry() -> int:
    if not sys.platform.startswith("linux"):
        print("Desktop entry install is only supported on Linux.")
        return 1

    exec_path = _resolve_exec_path()
    desktop_path = _desktop_file_path()
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text(_desktop_entry_text(exec_path), encoding="utf-8")

    for size in ICON_SIZES:
        source_icon = ICONSET_DIR / f"icon_{size}.png"
        target_icon = _icon_target_path(size)
        target_icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_icon, target_icon)

    _best_effort_run(["update-desktop-database", str(desktop_path.parent)])
    _best_effort_run(["gtk-update-icon-cache", "-f", "-t", str(_icons_root())])

    print(f"Installed desktop entry: {desktop_path}")
    print(f"Installed icons under: {_icons_root()}")
    return 0


def uninstall_desktop_entry() -> int:
    if not sys.platform.startswith("linux"):
        print("Desktop entry uninstall is only supported on Linux.")
        return 1

    desktop_path = _desktop_file_path()
    removed = 0

    if desktop_path.exists():
        desktop_path.unlink()
        removed += 1

    for size in ICON_SIZES:
        icon_path = _icon_target_path(size)
        if icon_path.exists():
            icon_path.unlink()
            removed += 1

    _best_effort_run(["update-desktop-database", str(desktop_path.parent)])
    _best_effort_run(["gtk-update-icon-cache", "-f", "-t", str(_icons_root())])

    if removed == 0:
        print("No desktop entry or icons found to remove.")
    else:
        print(f"Removed desktop assets for {APP_NAME}.")

    return 0
