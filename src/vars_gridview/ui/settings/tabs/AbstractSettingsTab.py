from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.settings import SettingsManager


class AbstractSettingsTab(QtWidgets.QWidget):
    """
    Abstract settings tab.

    Contains a page of settings for the application.
    """

    settingsChanged = QtCore.pyqtSignal()

    def __init__(self, name: str, icon: Optional[QtGui.QIcon] = None, parent=None):
        super().__init__(parent)

        self._settings = SettingsManager.get_instance()

        self._name = name
        self._icon = icon

    @property
    def name(self):
        return self._name

    @property
    def icon(self) -> Optional[QtGui.QIcon]:
        return None

    def apply_settings(self):
        raise NotImplementedError()

    def _settings_changed(self):
        self.settingsChanged.emit()
