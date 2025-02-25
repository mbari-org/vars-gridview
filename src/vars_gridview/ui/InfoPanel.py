from typing import Optional

from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSlot

from vars_gridview.ui.JSONTree import JSONTree


class InfoPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, flags=Qt.WindowType.Widget)

        self._bounding_box_info_tree = JSONTree()
        self._image_info_tree = JSONTree()

        self._layout()

    def _layout(self) -> None:
        layout = QHBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self._bounding_box_info_tree, stretch=1)
        layout.addWidget(self._image_info_tree, stretch=1)

    @pyqtSlot(object)
    def setBoundingBoxInfo(self, data: dict) -> None:
        self._bounding_box_info_tree.set_data(data)

    @pyqtSlot(object)
    def setImageInfo(self, data: dict) -> None:
        self._image_info_tree.set_data(data)
