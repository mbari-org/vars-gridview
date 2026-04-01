"""Menu/toolbar composition for MainWindow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class MainWindowActions:
    """Actions exposed after menu setup for optional future reuse/testing."""

    settings: QtGui.QAction
    open_log_dir: QtGui.QAction
    query: QtGui.QAction
    next_page: QtGui.QAction
    previous_page: QtGui.QAction


class MainWindowMenuCoordinator:
    """Build and attach MainWindow menu bar + left toolbar."""

    def __init__(
        self, window: QtWidgets.QMainWindow, menu_bar: QtWidgets.QMenuBar
    ) -> None:
        self._window = window
        self._menu_bar = menu_bar

    def build(
        self,
        *,
        icons_dir: Path,
        on_open_settings,
        on_open_log_dir,
        on_query,
        on_next_page,
        on_previous_page,
    ) -> MainWindowActions:
        file_menu = self._menu_bar.addMenu("&File")
        query_menu = self._menu_bar.addMenu("&Query")
        if file_menu is None or query_menu is None:
            raise RuntimeError("Could not create main window menus")

        settings_action = self._create_action(
            "&Settings",
            icon_path=icons_dir / "gear-solid.svg",
            shortcut="Ctrl+,",
            callback=on_open_settings,
        )
        file_menu.addAction(settings_action)

        open_log_dir_action = self._create_action(
            "&Open Log Directory",
            icon_path=icons_dir / "folder-open-solid.svg",
            callback=on_open_log_dir,
        )
        file_menu.addAction(open_log_dir_action)

        query_action = self._create_action(
            "&Query",
            icon_path=icons_dir / "magnifying-glass-solid.svg",
            shortcut="Ctrl+Q",
            callback=on_query,
        )
        query_menu.addAction(query_action)

        next_page_action = self._create_action(
            "&Next Page",
            icon_path=icons_dir / "right-long-solid.svg",
            callback=on_next_page,
        )
        query_menu.addAction(next_page_action)

        previous_page_action = self._create_action(
            "&Previous Page",
            icon_path=icons_dir / "left-long-solid.svg",
            callback=on_previous_page,
        )
        query_menu.addAction(previous_page_action)

        toolbar = QtWidgets.QToolBar()
        toolbar.setObjectName("toolbar")
        toolbar.addAction(settings_action)
        toolbar.addAction(query_action)
        toolbar.addAction(next_page_action)
        toolbar.addAction(previous_page_action)
        toolbar.addAction(open_log_dir_action)
        toolbar.setIconSize(QtCore.QSize(16, 16))
        self._window.addToolBar(QtCore.Qt.ToolBarArea.LeftToolBarArea, toolbar)

        return MainWindowActions(
            settings=settings_action,
            open_log_dir=open_log_dir_action,
            query=query_action,
            next_page=next_page_action,
            previous_page=previous_page_action,
        )

    def _create_action(
        self,
        text: str,
        *,
        icon_path: Path,
        callback,
        shortcut: str | None = None,
    ) -> QtGui.QAction:
        action = QtGui.QAction(text, self._window)
        action.setIcon(QtGui.QIcon(str(icon_path)))
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        return action
