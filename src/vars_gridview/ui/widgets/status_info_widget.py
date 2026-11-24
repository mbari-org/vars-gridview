from PyQt6.QtWidgets import QSizePolicy, QWidget

from vars_gridview.ui.style import UiDimensions
from vars_gridview.ui.widgets.flow_layout import FlowLayout
from vars_gridview.ui.widgets.status_info_item import StatusInfoItem


class StatusInfoWidget(QWidget):
    """
    Widget to display information about the current query and view status.
    """

    def __init__(self, state: dict[str, str], parent=None) -> None:
        super().__init__(parent=parent)

        self._items = {}

        # Items wrap onto another line instead of widening the window pane.
        # This widget sits under the grid, so any width it demanded was taken
        # from the grid's pane, and the grid reflowed ("jumped") every time
        # the status text grew or shrank. Wrapping only changes the height,
        # which never changes the grid's column count.
        self._layout_obj = FlowLayout(spacing=UiDimensions.STATUS_WIDGET_SPACING)
        self._layout_obj.setContentsMargins(*UiDimensions.STATUS_WIDGET_MARGINS)
        self.setLayout(self._layout_obj)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

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

    def clear(self) -> None:
        self._items = {}
        # remove widgets from layout
        while self._layout_obj.count():
            item = self._layout_obj.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def update(self, state: dict[str, str]) -> None:
        added = False
        for label, value in state.items():
            if label in self._items:
                self._items[label].value = value
            else:
                self._items[label] = StatusInfoItem(label, value)
                added = True
        # Rebuild the layout only when an item was added; a value change
        # just updates its label in place.
        if added:
            self._layout()
