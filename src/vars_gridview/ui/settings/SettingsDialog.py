from typing import Tuple
from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog.

    Contains settings for the application.
    """

    applySettings = QtCore.pyqtSignal()
    """
    Signal emitted when the apply button is pressed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        # Create tab widget to hold settings pages
        self._tab_widget = QtWidgets.QTabWidget()

        # Create button box (OK, Apply, Cancel)
        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        ).pressed.connect(self.accept)
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).pressed.connect(self._on_apply_pressed)
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        ).pressed.connect(self.reject)

        # self.accepted.connect(self.close)
        self.accepted.connect(self._apply)
        self._needs_apply = False
        self._update_apply_enabled()

        # Arrange the dialog layout
        self._arrange()

    def _arrange(self) -> None:
        """
        Arrange the widget.
        """
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self._tab_widget)
        layout.addWidget(self._button_box)

        self.setLayout(layout)

    def _update_apply_enabled(self) -> None:
        """
        Update the enabled state of the apply button.
        """
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).setEnabled(self._needs_apply)

    @QtCore.pyqtSlot()
    def _on_settings_changed(self) -> None:
        self._needs_apply = True
        self._update_apply_enabled()

    @QtCore.pyqtSlot()
    def _on_apply_pressed(self) -> None:
        self._apply()

        self._needs_apply = False
        self._update_apply_enabled()

    @QtCore.pyqtSlot()
    def _apply(self) -> None:
        """
        Apply settings if needed.
        """
        if self._needs_apply:
            self.applySettings.emit()

    def register(self, *tabs: Tuple[AbstractSettingsTab]) -> None:
        """
        Register tabs with the dialog.

        Args:
            tabs (Tuple[AbstractSettingsTab]): The tab to register.
        """
        for tab in tabs:
            # Add tab to tab widget
            self._tab_widget.addTab(tab, tab.name)

            # Connect signals/slots
            tab.settingsChanged.connect(self._on_settings_changed)
            self.applySettings.connect(tab.apply_settings)
