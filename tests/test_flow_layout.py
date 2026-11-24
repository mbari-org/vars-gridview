"""FlowLayout vertical alignment within a line."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.widgets.flow_layout import FlowLayout


def _row(*, center: bool) -> tuple[QtWidgets.QWidget, list[QtWidgets.QWidget]]:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    row = QtWidgets.QWidget()
    flow = FlowLayout(row, spacing=10, center_vertically=center)
    flow.setContentsMargins(0, 0, 0, 0)
    widgets = []
    for height in (20, 32, 16):
        w = QtWidgets.QWidget()
        w.setFixedSize(40, height)
        flow.addWidget(w)
        widgets.append(w)
    flow.setGeometry(QtCore.QRect(0, 0, 500, 32))
    return row, widgets


def test_items_top_aligned_by_default() -> None:
    _row_widget, widgets = _row(center=False)
    assert [w.geometry().top() for w in widgets] == [0, 0, 0]


def test_items_centred_on_their_line() -> None:
    _row_widget, widgets = _row(center=True)
    centres = [w.geometry().top() + w.height() / 2 for w in widgets]
    assert centres == [16, 16, 16]
