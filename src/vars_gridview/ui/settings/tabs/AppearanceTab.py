from PyQt6 import QtWidgets

from vars_gridview.lib.config.constants import SETTINGS
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab
from vars_gridview.ui.style import THEME_DEFAULT, THEME_OPTIONS


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
            self._on_setting_selection_color_changed
        )

        self.theme_combo_box = QtWidgets.QComboBox()
        for label, value in THEME_OPTIONS:
            self.theme_combo_box.addItem(label, value)
        self._set_theme_combo_value(SETTINGS.gui_style.value)
        self.theme_combo_box.currentIndexChanged.connect(self.settingsChanged.emit)
        SETTINGS.gui_style.valueChanged.connect(self._set_theme_combo_value)

        self.label_font_size_spinbox.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.selection_highlight_color_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.theme_combo_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.arrange()

    def select_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self._selection_highlight_color = color.name()
            self._update_selection_highlight_color_button()
            self.settingsChanged.emit()

    def _update_selection_highlight_color_button(self):
        self.selection_highlight_color_button.setStyleSheet(
            f"background-color: {self._selection_highlight_color};"
        )

    def _on_setting_selection_color_changed(self, color: str) -> None:
        self._selection_highlight_color = str(color)
        self._update_selection_highlight_color_button()

    def _set_theme_combo_value(self, theme_name: str) -> None:
        theme_name = str(theme_name).lower()
        idx = self.theme_combo_box.findData(theme_name)
        if idx < 0:
            idx = self.theme_combo_box.findData(THEME_DEFAULT)
        prev = self.theme_combo_box.blockSignals(True)
        self.theme_combo_box.setCurrentIndex(idx)
        self.theme_combo_box.blockSignals(prev)

    def refresh_from_settings(self) -> None:
        prev_font = self.label_font_size_spinbox.blockSignals(True)
        self.label_font_size_spinbox.setValue(SETTINGS.label_font_size.value)
        self.label_font_size_spinbox.blockSignals(prev_font)

        self._selection_highlight_color = SETTINGS.selection_highlight_color.value
        self._update_selection_highlight_color_button()

        self._set_theme_combo_value(SETTINGS.gui_style.value)

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        layout.addRow("Label font size", self.label_font_size_spinbox)
        layout.addRow(
            "Selection highlight color", self.selection_highlight_color_button
        )
        layout.addRow("Theme", self.theme_combo_box)

        self.setLayout(layout)

    def apply_settings(self) -> set[str]:
        changed: set[str] = set()

        if SETTINGS.label_font_size.set_value(self.label_font_size_spinbox.value()):
            changed.add(SETTINGS.label_font_size.key)
        if SETTINGS.selection_highlight_color.set_value(
            self._selection_highlight_color
        ):
            changed.add(SETTINGS.selection_highlight_color.key)

        theme_name = self.theme_combo_box.currentData()
        if theme_name is not None:
            if SETTINGS.gui_style.set_value(str(theme_name)):
                changed.add(SETTINGS.gui_style.key)

        return changed
