from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.ui.FileSelectionLineEdit import DirectorySelectionLineEdit
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class CacheTab(AbstractSettingsTab):
    """
    Cache tab.
    """

    clearCache = QtCore.pyqtSignal()

    def __init__(self, clear_cache_slot, parent=None):
        super().__init__("Cache", parent=parent)

        self.clearCache.connect(clear_cache_slot)

        self.cache_dir_lineedit = DirectorySelectionLineEdit(parent=self)
        self.cache_dir_lineedit.setText(SETTINGS.cache_dir.value)
        self.cache_dir_lineedit.textChanged.connect(self.settingsChanged.emit)
        SETTINGS.cache_dir.valueChanged.connect(self.cache_dir_lineedit.setText)

        self.cache_dir_lineedit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.clear_cache_button = QtWidgets.QPushButton("Clear cache")
        self.clear_cache_button.clicked.connect(self.clearCache.emit)
        self.clear_cache_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.arrange()

    def arrange(self):
        root_layout = QtWidgets.QVBoxLayout()

        form_layout = QtWidgets.QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        form_layout.addRow("Cache directory", self.cache_dir_lineedit)

        root_layout.addLayout(form_layout)
        root_layout.addWidget(self.clear_cache_button)

        self.setLayout(root_layout)

    def apply_settings(self):
        SETTINGS.cache_dir.value = self.cache_dir_lineedit.text()
