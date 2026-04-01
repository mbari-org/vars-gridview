from PyQt6 import QtWidgets

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class M3Tab(AbstractSettingsTab):
    """
    M3 microservices tab.
    """

    def __init__(self, settings: AppSettings | None = None, parent=None):
        super().__init__("M3", parent=parent)
        self._settings = settings or get_settings()

        self.raziel_url_edit = QtWidgets.QLineEdit(self._settings.raz_url.value)
        self.raziel_url_edit.textChanged.connect(self.settingsChanged.emit)
        self._settings.raz_url.valueChanged.connect(self.raziel_url_edit.setText)

        self.raziel_url_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.arrange()

    def refresh_from_settings(self) -> None:
        previous = self.raziel_url_edit.blockSignals(True)
        self.raziel_url_edit.setText(self._settings.raz_url.value)
        self.raziel_url_edit.blockSignals(previous)

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        layout.addRow("Raziel URL", self.raziel_url_edit)

        self.setLayout(layout)

    def apply_settings(self) -> set[str]:
        changed: set[str] = set()
        if self._settings.raz_url.set_value(self.raziel_url_edit.text()):
            changed.add(self._settings.raz_url.key)
        return changed
