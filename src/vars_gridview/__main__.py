"""
VARS GridView application entrypoint.
"""

import argparse
import logging
import sys
import traceback
from typing import Optional, Sequence

import pyqtgraph as pg
from PyQt6 import QtWidgets, QtGui, QtCore

from vars_gridview.lib.config.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
    ICONS_DIR,
    get_settings,
)
from vars_gridview.lib.runtime.desktop_entry import (
    install_desktop_entry,
    uninstall_desktop_entry,
)
from vars_gridview.lib.runtime.log import LOGGER, AppLogger


def parse_args(
    argv: Optional[Sequence[str]] = None,
) -> tuple[argparse.Namespace, list[str]]:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging to console"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "install-desktop",
        help="Install user-level Linux desktop entry and icons.",
    )
    subparsers.add_parser(
        "uninstall-desktop",
        help="Remove user-level Linux desktop entry and icons.",
    )

    cli_args = list(argv) if argv is not None else sys.argv[1:]
    args, qt_args = parser.parse_known_args(cli_args)
    return args, qt_args


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Main entrypoint.
    """
    # Parse command line arguments
    args, qt_args = parse_args(argv)

    if args.command == "install-desktop":
        return install_desktop_entry()
    if args.command == "uninstall-desktop":
        return uninstall_desktop_entry()

    # Set up logging
    if args.verbose:
        AppLogger.get_instance().set_stream_level(logging.DEBUG)

    LOGGER.info(f"Starting {APP_NAME} v{APP_VERSION}")

    # Use standard (row, col) image array order and antialiased rendering for
    # all pyqtgraph views, so image/ROI display matches plain numpy/OpenCV
    # image coordinates without manual rotation or axis-flip math.
    pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)

    # Create the Qt application
    app = QtWidgets.QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    # Show the splash icon
    splash_pixmap = QtGui.QPixmap(
        str(ICONS_DIR / "VARSGridView.iconset" / "icon_256.png")
    )
    splash = QtWidgets.QSplashScreen(splash_pixmap)
    splash.show()

    # Process events multiple times and add a small delay to ensure splash is rendered
    for _ in range(10):
        app.processEvents()
        QtCore.QThread.msleep(10)

    # Create the main window and show it
    try:
        from vars_gridview.ui.MainWindow import MainWindow

        main = MainWindow(app, settings=get_settings())
        main.show()
        splash.finish(main)
    except Exception as e:
        LOGGER.critical(f"Could not create main window: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        return 1

    # Exit after app is finished
    try:
        status = app.exec()
    except Exception as e:
        LOGGER.critical(f"Fatal exception: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        status = 1

    return status


if __name__ == "__main__":
    sys.exit(main())
