from PyQt6 import QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class M3Tab(AbstractSettingsTab):
    """
    M3 microservices tab.
    """

    def __init__(self, parent=None):
        super().__init__("M3", parent=parent)

        self.raziel_url_edit = QtWidgets.QLineEdit(self._settings.raz_url.value)
        self.raziel_url_edit.textChanged.connect(self.settingsChanged.emit)

        self.arrange()

    def arrange(self):
        layout = QtWidgets.QFormLayout()

        layout.addRow("Raziel URL", self.raziel_url_edit)

        self.setLayout(layout)

    def apply_settings(self):
        self._settings.raz_url.value = self.raziel_url_edit.text()
