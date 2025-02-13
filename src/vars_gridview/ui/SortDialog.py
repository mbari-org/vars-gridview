"""
Sort dialog. Provides an input for the user to specify the sort order of the rect widgets (ROIs) in the grid view. Supports multiple sort criteria and precedence.
"""

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QInputDialog,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

import vars_gridview.lib.sort_methods as sm


class SortDialogItem(QListWidgetItem):
    def __init__(self, method: sm.SortMethod, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = method
        self.setText(method.NAME)


class SortDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.methods = [
            sm.RecordedTimestampSort,
            sm.AssociationUUIDSort,
            sm.ObservationUUIDSort,
            sm.ImageReferenceUUIDSort,
            sm.LabelSort,
            sm.WidthSort,
            sm.HeightSort,
            sm.AreaSort,
            sm.IntensityMeanSort,
            sm.IntensityVarianceSort,
            sm.HueMeanSort,
            sm.HueMeanCenterRegion,
            sm.HueVarianceSort,
            sm.DepthSort,
            sm.LaplacianVarianceSort,
            sm.LaplacianOfGaussianSort,
            sm.SobelSort,
            sm.CannySort,
            sm.FrequencyDomainSort,
            sm.VerifierSort,
            sm.ConfidenceSort,
        ]

        self.setWindowTitle("Sort")
        self.setLayout(QVBoxLayout())

        self._add_method_button = QPushButton("Add")
        self._add_method_button.clicked.connect(self._add_method)

        self._clear_methods_button = QPushButton("Clear")
        self._clear_methods_button.clicked.connect(self._clear_methods)

        self._ok_button = QPushButton("OK")
        self._ok_button.clicked.connect(self.accept)

        self._methods_list = QListWidget()
        self._methods_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._methods_list.setMovement(QListView.Movement.Snap)

        self._layout()

    def _layout(self):
        self.layout().addWidget(self._methods_list)
        self.layout().addWidget(self._add_method_button)
        self.layout().addWidget(self._clear_methods_button)
        self.layout().addWidget(self._ok_button)

    @pyqtSlot()
    def _add_method(self):
        method_names = [method.NAME for method in self.methods]
        remaining_method_names = [
            method_name
            for method_name in method_names
            if method_name
            not in [
                self._methods_list.item(idx).text()
                for idx in range(self._methods_list.count())
            ]
        ]
        method_name, ok = QInputDialog.getItem(
            self, "Add sort method", "Sort method", remaining_method_names
        )
        if not ok:
            return

        method_index = method_names.index(method_name)
        self._methods_list.addItem(SortDialogItem(self.methods[method_index]))

    @pyqtSlot()
    def _clear_methods(self):
        self._methods_list.clear()

    def _get_method(self) -> sm.SortMethod:
        if self._methods_list.count() == 0:
            return sm.NoopSort()
        elif self._methods_list.count() == 1:
            return self._methods_list.item(0).method
        else:
            methods = [
                self._methods_list.item(idx).method
                for idx in range(self._methods_list.count())
            ]
            return sm.SortMethodGroup(*methods)

    def accept(self) -> None:
        self.method = self._get_method()
        super().accept()

    def clear(self):
        """
        Clear the current sort methods from the dialog.
        """
        self._clear_methods()


if __name__ == "__main__":
    # Test code, just show the dialog
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = SortDialog(None)
    dialog.exec()
