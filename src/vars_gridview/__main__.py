"""
VARS GridView application entrypoint.
"""

import argparse
import logging
import sys
import traceback

from PyQt6 import QtWidgets

from vars_gridview.lib.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
)
from vars_gridview.lib.log import LOGGER, AppLogger
from vars_gridview.ui.MainWindow import MainWindow


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

    # Create the main window and show it
    try:
        main = MainWindow(app)
        main.show()

        # Show a warning that this is the non-MP4 proxy version
        QtWidgets.QMessageBox.warning(
            main,
            "VARS GridView - Source Video Version",
            "This version of VARS GridView fetches ROIs and images from the original source file that the annotations were created on.\n"
            "Be careful when opening and editing ROIs on MOV files that were corrected in GridView using the MP4 proxies, as the frame alignment may differ.",
        )
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
