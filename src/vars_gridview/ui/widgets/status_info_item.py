from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from vars_gridview.ui.style import UiDimensions, status_info_item_stylesheet

MAX_VALUE_WIDTH_PX = 360


class StatusInfoItem(QWidget):
    """
    A single item in the status info widget, consisting of a label and a value.
    Designed to be compact and visually encapsulated for use in a horizontal
    status bar.
    """

    def __init__(self, label: str, value: str, parent=None) -> None:
        super().__init__(parent=parent)

        # Create widgets
        self._label = QLabel(label)
        self._value = QLabel()
        self._full_value = ""

        # Assign object names
        self.setObjectName("StatusInfoItem")
        self._label.setObjectName("StatusInfoKey")
        self._value.setObjectName("StatusInfoValue")

        # Ensure the widget uses the stylesheet for its background/border
        # (Qt requires WA_StyledBackground to paint QWidget backgrounds from style sheets)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Compact size policies so items fit in a horizontal status bar
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._value.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        # Small paddings / alignment
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._value.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        self._layout()

        # Style the widget using object names for scoping
        self.setStyleSheet(status_info_item_stylesheet())
        self.value = value

    def _layout(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(*UiDimensions.STATUS_ITEM_MARGINS)
        layout.setSpacing(UiDimensions.STATUS_ITEM_SPACING)
        layout.addWidget(self._label)
        layout.addWidget(self._value)
        self.setLayout(layout)

    @property
    def value(self) -> str:
        return self._full_value

    @value.setter
    def value(self, value: str):
        # A long value (an operation description, say) is shortened with an
        # ellipsis, full text in the tooltip: an item as wide as its whole
        # text used to widen the grid's pane and make the grid reflow.
        self._full_value = value
        metrics = self._value.fontMetrics()
        shown = metrics.elidedText(
            value, Qt.TextElideMode.ElideMiddle, MAX_VALUE_WIDTH_PX
        )
        self._value.setText(shown)
        self._value.setToolTip(value if shown != value else "")
