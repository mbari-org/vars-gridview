"""
VARS GridView application entrypoint.
"""

import argparse
import functools
import logging
import sys
import traceback
from collections.abc import Sequence

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

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
    argv: Sequence[str] | None = None,
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


def install_exception_hook() -> None:
    """Log (and show) exceptions that escape Qt slots instead of aborting.

    With no ``sys.excepthook`` of its own, PyQt6 calls qFatal() on any
    exception raised in a slot, killing the app -- and with it any box edits
    not yet saved to VARS. Logging and carrying on keeps the session alive.
    """
    showing = False
    quitting = False
    dialogs: set[QtWidgets.QMessageBox] = set()  # keep open dialogs alive

    def on_dialog_closed(*_args) -> None:
        nonlocal showing
        showing = False

    def on_about_to_quit() -> None:
        nonlocal quitting
        quitting = True

    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(on_about_to_quit)

    def hook(exc_type, exc_value, exc_tb) -> None:
        nonlocal showing
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        LOGGER.error(f"Unhandled exception:\n{text}")
        app = QtWidgets.QApplication.instance()
        if (
            app is None
            or showing
            or quitting  # a dialog now would stop the app from quitting
            or app.closingDown()
            or QtCore.QThread.currentThread() is not app.thread()
        ):
            return
        showing = True  # one dialog at a time, not one per repeated failure
        try:
            box = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Warning,
                "Unexpected error",
                f"{exc_type.__name__}: {exc_value}\n\n"
                "The error was logged. GridView will keep running, but you may "
                "want to save your work and restart.",
            )
            box.setDetailedText(text)
            box.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            box.finished.connect(on_dialog_closed)
            # show(), not exec(): exec() runs a nested event loop inside the
            # failing slot, and when that slot was a QTimer.singleShot
            # callback the loop deleted the callback while PyQt was still
            # reporting its exception -- a segfault.
            box.show()
            dialogs.add(box)
            # partial, not a lambda: a lambda reads `dialogs` from this
            # closure, which may already be gone when a dialog still open at
            # shutdown is destroyed (NameError).
            box.destroyed.connect(functools.partial(dialogs.discard, box))
        except Exception:  # noqa: BLE001 -- the hook itself must never raise
            showing = False

    sys.excepthook = hook


def main(argv: Sequence[str] | None = None) -> int:
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
    install_exception_hook()
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
    except Exception as e:  # noqa: BLE001
        LOGGER.critical(f"Could not create main window: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        return 1

    # Exit after app is finished
    try:
        status = app.exec()
    except Exception as e:  # noqa: BLE001
        LOGGER.critical(f"Fatal exception: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        status = 1

    return status


if __name__ == "__main__":
    sys.exit(main())
