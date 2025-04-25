"""
JSON tree widget.
"""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QApplication


class JSONTree(QTreeWidget):
    def __init__(self, json_data=None, parent=None):
        super(JSONTree, self).__init__(parent)
        self.setHeaderHidden(True)
        self.setHeaderLabels(("key", "value"))
        self.set_data(json_data)

    def set_data(self, json_data):
        self.clear()
        if json_data is not None:
            self._parse_json(json_data)
        self.resizeColumnToContents(0)
        self.expandAll()

    def _parse_json(self, json_el, parent=None):
        if parent is None:  # Root node
            parent = self

        if isinstance(json_el, list):  # If a list, remap it to a dict
            json_el = dict(enumerate(json_el))

        for key, val in json_el.items():
            item = QTreeWidgetItem(parent)
            item.setText(0, str(key))
            if isinstance(val, dict) or isinstance(val, list):
                self._parse_json(val, parent=item)
            else:
                item.setText(1, str(val))

    def mousePressEvent(self, e):
        # If right-clicked, add a context menu to copy value
        if e.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(e.pos())
            if item:
                self.setCurrentItem(item)
                menu = QMenu()
                menu.addAction(
                    "Copy value", lambda: QApplication.clipboard().setText(item.text(1))
                )
                menu.exec(e.globalPosition().toPoint())
        super(JSONTree, self).mousePressEvent(e)
