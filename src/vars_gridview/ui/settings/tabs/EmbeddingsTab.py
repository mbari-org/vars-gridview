from PyQt6 import QtWidgets

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class EmbeddingsTab(AbstractSettingsTab):
    """
    Embeddings tab.
    """

    def __init__(self, parent=None):
        super().__init__("Embeddings", parent=parent)

        self._embeddings_enabled_toggle = QtWidgets.QCheckBox()
        self._embeddings_enabled_toggle.setChecked(SETTINGS.embeddings_enabled.value)
        self._embeddings_enabled_toggle.stateChanged.connect(self.settingsChanged.emit)
        SETTINGS.embeddings_enabled.valueChanged.connect(
            self._embeddings_enabled_toggle.setChecked
        )

        self.arrange()

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        layout.addRow("Embeddings enabled", self._embeddings_enabled_toggle)

        self.setLayout(layout)

    def apply_settings(self):
        SETTINGS.embeddings_enabled.value = self._embeddings_enabled_toggle.isChecked()
