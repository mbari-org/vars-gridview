from PyQt6 import QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class AppearanceTab(AbstractSettingsTab):
    """
    Application appearance tab.
    """

    def __init__(self, parent=None):
        super().__init__("Appearance", parent=parent)

        self.label_font_size_spinbox = QtWidgets.QSpinBox()
        self.label_font_size_spinbox.setMinimum(4)
        self.label_font_size_spinbox.setMaximum(12)
        self.label_font_size_spinbox.setValue(self._settings.label_font_size.value)
        self.label_font_size_spinbox.valueChanged.connect(self.settingsChanged.emit)
        self._settings.label_font_size.valueChanged.connect(
            self.label_font_size_spinbox.setValue
        )

        self.arrange()

    def arrange(self):
        layout = QtWidgets.QFormLayout()

        layout.addRow("Label font size", self.label_font_size_spinbox)

        self.setLayout(layout)

    def apply_settings(self):
        self._settings.label_font_size.value = self.label_font_size_spinbox.value()
