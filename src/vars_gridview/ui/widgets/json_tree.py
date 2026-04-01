"""Expandable JSON tree widget with right-click copy support."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMenu, QTreeWidget, QTreeWidgetItem


class JSONTree(QTreeWidget):
    """Read-only tree widget that visualises a JSON-serialisable value.

    Nested dicts and lists are shown as tree branches; scalar values appear
    in the second column next to their key.

    Args:
        json_data: Initial data to display.  Pass ``None`` to start empty.
        parent: Optional parent widget.
    """

    def __init__(
        self, json_data: Any = None, parent: QTreeWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setHeaderLabels(("key", "value"))
        self.set_data(json_data)

    def set_data(self, json_data: Any) -> None:
        """Replace the displayed data with *json_data*.

        Args:
            json_data: Any JSON-serialisable value, or ``None`` to clear.
        """
        self.clear()
        if json_data is not None:
            self._parse_json(json_data)
        self.resizeColumnToContents(0)
        self.expandAll()

    def _parse_json(
        self, json_el: Any, parent: QTreeWidget | QTreeWidgetItem | None = None
    ) -> None:
        """Recursively populate the tree from *json_el*.

        Args:
            json_el: The element to render (dict, list, or scalar).
            parent: Parent tree node; defaults to ``self`` for the root.
        """
        if parent is None:
            parent = self
        if isinstance(json_el, list):
            json_el = dict(enumerate(json_el))
        for key, val in json_el.items():
            item = QTreeWidgetItem(parent)
            item.setText(0, str(key))
            if isinstance(val, (dict, list)):
                self._parse_json(val, parent=item)
            else:
                item.setText(1, str(val))

    def mousePressEvent(self, e: QMouseEvent) -> None:  # type: ignore[override]
        """Show a context menu on right-click to copy the item's value."""
        if e.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(e.pos())
            if item:
                self.setCurrentItem(item)
                menu = QMenu()
                menu.addAction(
                    "Copy value",
                    lambda: QApplication.clipboard().setText(item.text(1)),
                )
                menu.exec(e.globalPosition().toPoint())
        super().mousePressEvent(e)
