from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QCompleter,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ControlBar(QWidget):
    zoomUpdated = pyqtSignal(int)
    hideLabeledUpdated = pyqtSignal(bool)
    hideUnlabeledUpdated = pyqtSignal(bool)
    sortRequested = pyqtSignal()
    openVideoRequested = pyqtSignal()
    conceptSelected = pyqtSignal(str)
    partSelected = pyqtSignal(str)
    labelRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    verifyRequested = pyqtSignal()
    unverifyRequested = pyqtSignal()
    deleteRequested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, flags=Qt.WindowType.Widget)

        self._zoom_label = QLabel("Zoom")
        self._zoom_spinbox = QSpinBox()
        self._zoom_spinbox.setRange(20, 200)
        self._zoom_spinbox.setSingleStep(20)
        self._zoom_spinbox.setValue(60)

        self._hide_labeled_checkbox = QCheckBox("Hide Labeled")
        self._hide_labeled_checkbox.setChecked(False)
        self._hide_unlabeled_checkbox = QCheckBox("Hide Unlabeled")
        self._hide_unlabeled_checkbox.setChecked(False)

        self._sort_button = QPushButton("Sort")
        self._open_video_button = QPushButton("Open Video")

        self._concept_combobox = QComboBox()
        self._concept_combobox.setEditable(True)
        self._concept_combobox.lineEdit().setPlaceholderText("Concept")
        self._concept_combobox.completer().setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._concept_combobox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._concept_combobox.setCurrentIndex(-1)
        self._part_combobox = QComboBox()
        self._part_combobox.setEditable(True)
        self._part_combobox.lineEdit().setPlaceholderText("Part")
        self._part_combobox.completer().setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._part_combobox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._part_combobox.setCurrentIndex(-1)

        self._label_button = QPushButton("Label")
        self._clear_button = QPushButton("Clear")
        self._verify_button = QPushButton("Verify")
        self._unverify_button = QPushButton("Unverify")
        self._delete_button = QPushButton("Delete")

        self._style()
        self._connect()
        self._layout()

    def _style(self) -> None:
        """
        Style elements.
        """
        # Action buttons use system defaults
        self._sort_button.setAutoFillBackground(True)
        self._open_video_button.setAutoFillBackground(True)

        # Label button uses system highlight colors
        self._label_button.setStyleSheet("""
            QPushButton {
                background-color: palette(highlight);
                color: palette(highlighted-text);
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: palette(dark);
            }
            QPushButton:disabled {
                background-color: palette(mid);
                color: palette(disabled-text);
            }
        """)

        # Clear button uses neutral system colors
        self._clear_button.setStyleSheet("""
            QPushButton {
                background-color: palette(mid);
                color: palette(window-text);
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: palette(dark);
            }
        """)

        # Verify button with guaranteed readable green
        self._verify_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: black;
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)

        # Unverify button with guaranteed readable yellow
        self._unverify_button.setStyleSheet("""
            QPushButton {
                background-color: #f1c40f;
                color: black;
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
        """)

        # Delete button with guaranteed readable red
        self._delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 4px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #ecf0f1;
            }
        """)

    def _connect(self) -> None:
        """
        Connect signals and slots.
        """
        self._zoom_spinbox.valueChanged.connect(self.zoomUpdated.emit)
        self._hide_labeled_checkbox.stateChanged.connect(self.hideLabeledUpdated.emit)
        self._hide_unlabeled_checkbox.stateChanged.connect(
            self.hideUnlabeledUpdated.emit
        )
        self._sort_button.clicked.connect(self.sortRequested.emit)
        self._open_video_button.clicked.connect(self.openVideoRequested.emit)
        self._concept_combobox.activated.connect(
            lambda index: self.conceptSelected.emit(
                self._concept_combobox.itemText(index)
            )
        )
        self._part_combobox.activated.connect(
            lambda index: self.partSelected.emit(self._part_combobox.itemText(index))
        )
        self._label_button.clicked.connect(self.labelRequested.emit)
        self._clear_button.clicked.connect(self.clearRequested.emit)
        self._verify_button.clicked.connect(self.verifyRequested.emit)
        self._unverify_button.clicked.connect(self.unverifyRequested.emit)
        self._delete_button.clicked.connect(self.deleteRequested.emit)

    def _layout(self) -> None:
        """
        Lay out the widget.
        """
        layout = QHBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self._zoom_label)
        layout.addWidget(self._zoom_spinbox)
        layout.addWidget(self._hide_labeled_checkbox)
        layout.addWidget(self._hide_unlabeled_checkbox)
        layout.addWidget(self._sort_button)
        layout.addWidget(self._open_video_button)

        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        layout.addSpacerItem(spacer)

        layout.addWidget(self._concept_combobox)
        layout.addWidget(self._part_combobox)
        layout.addWidget(self._label_button)
        layout.addWidget(self._clear_button)
        layout.addWidget(self._verify_button)
        layout.addWidget(self._unverify_button)
        layout.addWidget(self._delete_button)


def _test() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication([])

    control_bar = ControlBar()

    # Define dummy slots for testing.
    control_bar.zoomUpdated.connect(lambda value: print(f"Zoom updated: {value}"))
    control_bar.hideLabeledUpdated.connect(
        lambda value: print(f"Hide labeled updated: {value}")
    )
    control_bar.hideUnlabeledUpdated.connect(
        lambda value: print(f"Hide unlabeled updated: {value}")
    )
    control_bar.sortRequested.connect(lambda: print("Sort requested"))
    control_bar.openVideoRequested.connect(lambda: print("Open video requested"))
    control_bar.conceptSelected.connect(
        lambda value: print(f"Concept updated: {value}")
    )
    control_bar.partSelected.connect(lambda value: print(f"Part updated: {value}"))
    control_bar.labelRequested.connect(lambda: print("Label requested"))
    control_bar.clearRequested.connect(lambda: print("Clear requested"))
    control_bar.verifyRequested.connect(lambda: print("Verify requested"))
    control_bar.unverifyRequested.connect(lambda: print("Unverify requested"))
    control_bar.deleteRequested.connect(lambda: print("Delete requested"))

    control_bar.show()

    app.exec()


if __name__ == "__main__":
    _test()


__all__ = ["ControlBar"]
