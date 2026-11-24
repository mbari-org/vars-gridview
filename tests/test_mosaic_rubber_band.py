"""Drag-selecting tiles: hit-testing through the scene index, and no work on
moves that don't change which tiles are under the band."""

from __future__ import annotations

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.ui.coordinators.mosaic_rubber_band import MosaicRubberBandSelector

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

TILE = 50  # tiles are 50 x 50, 10 to a row, no gaps


class _Selection:
    def __init__(self) -> None:
        self.selected: list = []
        self.sets = 0

    def is_selected(self, widget) -> bool:
        return widget in self.selected

    def set_selection(self, widgets: list) -> None:
        self.sets += 1
        self.selected = list(widgets)


def _mouse(kind, x: float, y: float, buttons=QtCore.Qt.MouseButton.LeftButton):
    button = (
        QtCore.Qt.MouseButton.NoButton
        if kind == QtCore.QEvent.Type.MouseMove
        else QtCore.Qt.MouseButton.LeftButton
    )
    return QtGui.QMouseEvent(
        kind,
        QtCore.QPointF(x, y),
        QtCore.QPointF(x, y),
        button,
        buttons,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def grid():
    scene = QtWidgets.QGraphicsScene(0, 0, 500, 500)
    view = QtWidgets.QGraphicsView(scene)
    view.setFixedSize(520, 520)
    view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    container = QtWidgets.QGraphicsWidget()  # like the grid's layout widget
    scene.addItem(container)
    tiles = []
    for i in range(100):
        tile = QtWidgets.QGraphicsRectItem(0, 0, TILE, TILE, container)
        tile.setPos((i % 10) * TILE, (i // 10) * TILE)
        tiles.append(tile)
    hidden = tiles[1]
    hidden.hide()  # filtered out
    shown = [t for t in tiles if t is not hidden]
    selection = _Selection()
    selector = MosaicRubberBandSelector(
        parent=view,
        graphics_view=view,
        selection_model=selection,
        visible_widgets_getter=lambda: shown,
    )
    view.show()
    QtWidgets.QApplication.processEvents()
    view.centerOn(250, 250)

    def at(scene_x: float, scene_y: float) -> QtCore.QPointF:
        return QtCore.QPointF(view.mapFromScene(QtCore.QPointF(scene_x, scene_y)))

    return view, tiles, selection, selector, at


def test_drag_selects_touched_tiles_in_grid_order(grid) -> None:
    view, tiles, selection, selector, at = grid
    viewport = view.viewport()
    start, end = at(5, 5), at(120, 70)  # tiles in columns 0-2 of rows 0-1
    selector.eventFilter(
        viewport, _mouse(QtCore.QEvent.Type.MouseButtonPress, start.x(), start.y())
    )
    selector.eventFilter(
        viewport, _mouse(QtCore.QEvent.Type.MouseMove, end.x(), end.y())
    )
    # tiles[1] is hidden by a filter, so it isn't selected.
    assert selection.selected == [tiles[0], tiles[2], tiles[10], tiles[11], tiles[12]]


def test_moves_within_the_same_tiles_dont_reselect(grid) -> None:
    view, _tiles, selection, selector, at = grid
    viewport = view.viewport()
    start = at(5, 5)
    selector.eventFilter(
        viewport, _mouse(QtCore.QEvent.Type.MouseButtonPress, start.x(), start.y())
    )
    for x in (60, 70, 80, 90):  # all inside the second column of tiles
        p = at(x, 20)
        selector.eventFilter(
            viewport, _mouse(QtCore.QEvent.Type.MouseMove, p.x(), p.y())
        )
    assert selection.sets == 1


def test_drag_from_a_selected_tile_deselects(grid) -> None:
    view, tiles, selection, selector, at = grid
    viewport = view.viewport()
    selection.selected = [tiles[0], tiles[2], tiles[50]]
    start, end = at(5, 5), at(120, 20)
    selector.eventFilter(
        viewport, _mouse(QtCore.QEvent.Type.MouseButtonPress, start.x(), start.y())
    )
    selector.eventFilter(
        viewport, _mouse(QtCore.QEvent.Type.MouseMove, end.x(), end.y())
    )
    assert selection.selected == [tiles[50]]
