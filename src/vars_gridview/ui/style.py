"""Central UI style tokens and helpers.

This module collects reusable UI constants (sizes, spacing, colors, theme IDs)
and exposes small helpers for applying app-level themes and widget-level styles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import qdarkstyle
from PyQt6 import QtCore, QtGui, QtWidgets

THEME_DEFAULT = "default"
THEME_DARKBREEZE = "darkbreeze"
THEME_DARKSTYLE = "darkstyle"

THEME_OPTIONS: list[tuple[str, str]] = [
    ("Default", THEME_DEFAULT),
    ("DarkBreeze", THEME_DARKBREEZE),
    ("DarkStyle", THEME_DARKSTYLE),
]


class UiDimensions:
    """Shared numeric dimensions for dialogs and compact status widgets."""

    DIALOG_MIN_WIDTH = 400
    STATUS_WIDGET_MARGINS = (2, 0, 2, 0)
    STATUS_WIDGET_SPACING = 6
    STATUS_ITEM_MARGINS = (4, 2, 4, 2)
    STATUS_ITEM_SPACING = 2
    MOSAIC_LAYOUT_MARGINS = (0, 0, 0, 0)
    MOSAIC_LAYOUT_SPACING = 0


class UiTypography:
    """Shared font sizes used by the main window layout."""

    BASE_POINT_SIZE = 8
    CONTROL_POINT_SIZE = 10
    INFO_PANEL_POINT_SIZE = 12


class UiGeometry:
    """Programmatic MainWindow baseline geometry and sizing tokens."""

    WINDOW_WIDTH = 1920
    WINDOW_HEIGHT = 1079
    MENU_BAR_HEIGHT = 19
    ROI_GRAPHICS_MIN_WIDTH = 320
    ZOOM_SPINBOX_MAX_WIDTH = 60
    ZOOM_MIN = 20
    ZOOM_MAX = 200
    ZOOM_STEP = 10
    ZOOM_DEFAULT = 60


@dataclass(frozen=True)
class ActionButtonPalette:
    """Semantic colors for top-level action buttons."""

    label: str = "#085d8e"
    verify: str = "#088e0d"
    unverify: str = "#8e4708"
    mark_training: str = "#088e8e"
    unmark_training: str = "#8e8e08"
    delete: str = "#8f0808"


ACTION_BUTTON_PALETTE = ActionButtonPalette()
DEFAULT_SELECTION_HIGHLIGHT_COLOR = "#34a1eb"


def action_button_style(hex_color: str) -> str:
    """Return a simple stylesheet for semantic action-button background color."""
    return f"background-color: {hex_color};"


def status_info_item_stylesheet() -> str:
    """Return scoped stylesheet for `StatusInfoItem` tiles."""
    return """
            QWidget#StatusInfoItem {
              border: 1px solid rgba(255,255,255,0.08);
              background: rgba(255,255,255,0.01);
              border-radius: 6px;
              padding-left: 6px;
              padding-right: 6px;
            }
            QLabel#StatusInfoKey {
              color: rgba(255,255,255,0.85);
              font-weight: 600;
              padding-right: 6px;
            }
            QLabel#StatusInfoValue {
              color: rgba(255,255,255,0.9);
              font-weight: 400;
            }
            """


def control_font() -> QtGui.QFont:
    """Return the common bold control font used in MainWindow controls."""
    font = QtGui.QFont()
    font.setPointSize(UiTypography.CONTROL_POINT_SIZE)
    font.setBold(True)
    return font


def apply_app_theme(
    app: QtWidgets.QApplication,
    theme_name: str,
    style_dir: Path,
) -> None:
    """Apply application stylesheet by stable theme ID.

    Args:
        app: Running QApplication.
        theme_name: One of THEME_* constants.
        style_dir: Directory containing bundled QSS files.
    """
    style_name = str(theme_name).lower()
    if style_name == THEME_DARKSTYLE:
        # qdarkstyle relies on this variable to pick a Qt wrapper backend.
        import os

        os.environ["PYQTGRAPH_QT_LIB"] = "PyQt6"
        app.setStyleSheet(
            qdarkstyle.load_stylesheet(qt_api=os.environ["PYQTGRAPH_QT_LIB"])
        )
        return

    if style_name == THEME_DARKBREEZE:
        file = QtCore.QFile(str(style_dir / "dark.qss"))
        file.open(QtCore.QFile.OpenModeFlag.ReadOnly | QtCore.QFile.OpenModeFlag.Text)
        stream = QtCore.QTextStream(file)
        app.setStyleSheet(stream.readAll())
        return

    app.setStyleSheet("")
