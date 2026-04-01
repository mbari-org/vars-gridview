from typing import Optional

from PyQt6 import QtCore, QtWidgets


class AbstractSettingsTab(QtWidgets.QWidget):
    """
    Abstract settings tab.

    Contains a page of settings for the application.
    """

    settingsChanged = QtCore.pyqtSignal()
    """
    Signal emitted when settings are changed.
    """

    def __init__(self, name: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._name = name

    @property
    def name(self):
        return self._name

    def apply_settings(self) -> set[str]:
        """
        Apply values from the tab to settings and return changed keys.

        Returns:
            Set of ``QSettings`` keys that changed during apply.
        """
        raise NotImplementedError()

    def refresh_from_settings(self) -> None:
        """Refresh UI controls from persisted settings values."""

    def _settings_changed(self):
        """
        Called when settings are changed. Emits settingsChanged.
        """
        self.settingsChanged.emit()
