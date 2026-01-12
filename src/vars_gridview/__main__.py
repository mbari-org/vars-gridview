"""
VARS GridView application entrypoint.
"""

import argparse
import logging
import sys
import traceback

from PyQt6 import QtWidgets, QtGui, QtCore

from vars_gridview.lib.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
    ICONS_DIR,
)
from vars_gridview.lib.log import LOGGER, AppLogger


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging to console"
    )
    return parser.parse_args()


def main():
    """
    Main entrypoint.
    """
    # Parse command line arguments
    args = parse_args()

    # Set up logging
    if args.verbose:
        AppLogger.get_instance().set_stream_level(logging.DEBUG)

    LOGGER.info(f"Starting {APP_NAME} v{APP_VERSION}")

    # Create the Qt application
    app = QtWidgets.QApplication(sys.argv)
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

        main = MainWindow(app)
        main.show()
        splash.finish(main)
    except Exception as e:
        LOGGER.critical(f"Could not create main window: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        sys.exit(1)

    # Exit after app is finished
    try:
        status = app.exec()
    except Exception as e:
        LOGGER.critical(f"Fatal exception: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        status = 1

    sys.exit(status)


if __name__ == "__main__":
    main()
