from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab
from vars_gridview.ui.style import UiDimensions


class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog.

    Contains settings for the application.
    """

    settingsApplied = QtCore.pyqtSignal(list)
    """Signal emitted with a list of changed setting keys after apply."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setMinimumWidth(UiDimensions.DIALOG_MIN_WIDTH)

        # Create tab widget to hold settings pages
        self._tab_widget = QtWidgets.QTabWidget()
        self._tabs: list[AbstractSettingsTab] = []

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
        if not self._needs_apply:
            return

        changed_keys: set[str] = set()
        for tab in self._tabs:
            changed_keys.update(tab.apply_settings())

        if changed_keys:
            self.settingsApplied.emit(sorted(changed_keys))

    def register(self, *tabs: AbstractSettingsTab) -> None:
        """
        Register tabs with the dialog.

        Args:
            tabs (Tuple[AbstractSettingsTab]): The tab to register.
        """
        for tab in tabs:
            self._tabs.append(tab)
            # Add tab to tab widget
            self._tab_widget.addTab(tab, tab.name)

            # Connect signals/slots
            tab.settingsChanged.connect(self._on_settings_changed)

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Refresh tab widgets from persisted settings whenever dialog opens."""
        for tab in self._tabs:
            tab.refresh_from_settings()
        self._needs_apply = False
        self._update_apply_enabled()
        super().showEvent(event)
