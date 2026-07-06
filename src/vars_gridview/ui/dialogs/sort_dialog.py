"""Sort dialog for the image mosaic.

Provides a reorderable list of :class:`~vars_gridview.lib.sorting.sort_methods.SortMethod`
criteria.  The user can add, remove, and drag-to-reorder methods; accepting the
dialog exposes the resulting composite sort as :attr:`SortDialog.method`.
"""

from __future__ import annotations

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
    QWidget,
)

import vars_gridview.lib.sorting.sort_methods as sm


class SortDialogItem(QListWidgetItem):
    """List item that carries a :class:`~vars_gridview.lib.sorting.sort_methods.SortMethod` reference."""

    def __init__(self, method: type[sm.SortMethod], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.method = method
        self.setText(method.NAME)


class SortDialog(QDialog):
    """Dialog for composing a multi-criteria sort order.

    After :meth:`accept` the chosen composite method is available as
    :attr:`method`.
    """

    def __init__(self, parent: QWidget | None) -> None:
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
            sm.AspectRatioSort,
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
        self._ok_button.setDefault(True)
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

    def _get_method(self) -> type[sm.SortMethod] | sm.SortMethodGroup:
        """Build the composite sort method from the current list."""
        if self._methods_list.count() == 0:
            return sm.NoopSort
        if self._methods_list.count() == 1:
            return self._methods_list.item(0).method
        methods = [
            self._methods_list.item(idx).method
            for idx in range(self._methods_list.count())
        ]
        return sm.SortMethodGroup(*methods)

    def accept(self) -> None:
        self.method = self._get_method()
        super().accept()

    def clear(self) -> None:
        """Clear all sort methods from the dialog."""
        self._clear_methods()
