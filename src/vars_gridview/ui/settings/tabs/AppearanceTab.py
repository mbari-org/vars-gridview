from PyQt6 import QtWidgets

from vars_gridview.lib.constants import SETTINGS
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
        self.label_font_size_spinbox.setValue(SETTINGS.label_font_size.value)
        self.label_font_size_spinbox.valueChanged.connect(self.settingsChanged.emit)
        SETTINGS.label_font_size.valueChanged.connect(
            self.label_font_size_spinbox.setValue
        )

        self.selection_highlight_color_button = QtWidgets.QPushButton()
        self.selection_highlight_color_button.clicked.connect(self.select_color)
        self._selection_highlight_color = SETTINGS.selection_highlight_color.value
        self._update_selection_highlight_color_button()
        SETTINGS.selection_highlight_color.valueChanged.connect(
            self._update_selection_highlight_color_button
        )

        self.label_font_size_spinbox.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.selection_highlight_color_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.arrange()

    def select_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self._selection_highlight_color = color.name()
            SETTINGS.selection_highlight_color.value = self._selection_highlight_color

    def _update_selection_highlight_color_button(self):
        self.selection_highlight_color_button.setStyleSheet(
            f"background-color: {self._selection_highlight_color};"
        )

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        layout.addRow("Label font size", self.label_font_size_spinbox)
        layout.addRow(
            "Selection highlight color", self.selection_highlight_color_button
        )

        self.setLayout(layout)

    def apply_settings(self):
        SETTINGS.label_font_size.value = self.label_font_size_spinbox.value()
        SETTINGS.selection_highlight_color.value = self._selection_highlight_color
