from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt


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
        self._value = QLabel(value)

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
        self.setStyleSheet(
            """
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
        )

    def _layout(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._value)
        self.setLayout(layout)

    @property
    def value(self) -> str:
        return self._value.text()

    @value.setter
    def value(self, value: str):
        self._value.setText(value)
