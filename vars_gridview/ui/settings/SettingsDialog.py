from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab
from vars_gridview.ui.settings.tabs.M3Tab import M3Tab
from vars_gridview.ui.settings.tabs.SQLTab import SQLTab


class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog.

    Contains settings for the application.
    """

    applySettings = QtCore.pyqtSignal()

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

        # Add tabs
        self._add_tabs()

        # Arrange the dialog layout
        self._arrange()

    def _arrange(self):
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self._tab_widget)
        layout.addWidget(self._button_box)

        self.setLayout(layout)

    def _update_apply_enabled(self):
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).setEnabled(self._needs_apply)

    def _on_settings_changed(self):
        self._needs_apply = True
        self._update_apply_enabled()

    def _on_apply_pressed(self):
        self._apply()

        self._needs_apply = False
        self._update_apply_enabled()

    def _apply(self):
        if self._needs_apply:
            self.applySettings.emit()

    def _register_tab(self, tab: AbstractSettingsTab):
        # Add tab to tab widget
        if tab.icon is not None:
            self._tab_widget.addTab(tab, tab.icon, tab.name)
        else:
            self._tab_widget.addTab(tab, tab.name)

        # Connect signals/slots
        tab.settingsChanged.connect(self._on_settings_changed)
        self.applySettings.connect(tab.apply_settings)

    def _add_tabs(self):
        self._register_tab(M3Tab())
        self._register_tab(SQLTab())
