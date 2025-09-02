from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy

from vars_gridview.ui.StatusInfoItem import StatusInfoItem


class StatusInfoWidget(QWidget):
    """
    Widget to display information about the current query and view status.
    """

    def __init__(self, state: dict[str, str], parent=None) -> None:
        super().__init__(parent=parent)

        self._items = {}

        # Create a single layout object and attach it once. We'll reuse it
        # and clear/add child widgets as the state changes so we don't call
        # setLayout repeatedly.
        self._layout_obj = QHBoxLayout()
        self._layout_obj.setContentsMargins(2, 0, 2, 0)
        self._layout_obj.setSpacing(6)
        self.setLayout(self._layout_obj)

        # Compact size policy so it fits in a horizontal status bar
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        # Populate initial items
        self.update(state)

    def _layout(self) -> None:
        # clear existing widgets from the layout
        while self._layout_obj.count():
            item = self._layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        # add each StatusInfoItem
        for item in self._items.values():
            self._layout_obj.addWidget(item)

        # ensure remaining space is kept to the right
        self._layout_obj.addStretch()

    def clear(self) -> None:
        self._items = {}
        # remove widgets from layout
        while self._layout_obj.count():
            item = self._layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def update(self, state: dict[str, str]) -> None:
        for label, value in state.items():
            if label in self._items:
                self._items[label].value = value
            else:
                self._items[label] = StatusInfoItem(label, value)
        self._layout()
