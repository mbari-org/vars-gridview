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

    def apply_settings(self):
        """
        Apply values from the tab to the application settings. Subclasses should implement this method.
        """
        raise NotImplementedError()

    def _settings_changed(self):
        """
        Called when settings are changed. Emits settingsChanged.
        """
        self.settingsChanged.emit()
