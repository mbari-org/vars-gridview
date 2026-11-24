"""Click-and-drag selection over the mosaic (ported from mbari-ml).

Drag a rectangle over the grid to select every tile it touches. With Ctrl
(Cmd on macOS) held, each drag adds to the selection instead of replacing it,
so several separate drags build one selection. A drag that *starts on a tile
that is already selected* deselects instead: every tile it touches leaves the
selection and the rest stay selected.

It watches the view's viewport rather than the tiles: a press on a tile still
reaches it as an ordinary click (select / Ctrl-toggle, and the image view
updates), and only once the mouse moves past the platform drag distance does
it become a drag. Shift is left alone for Shift-click range selection.
Dragging past the top or bottom edge scrolls the grid.

Hit-testing uses the scene's spatial index (``QGraphicsScene.items``), not a
pass over every tile, and the selection is only replaced when the set of
tiles under the band changes -- so dragging stays smooth on large pages.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from vars_gridview.controllers.selection_model import SelectionModel

DRAG_AUTOSCROLL_STEP = 24  # pixels per mouse move past the top/bottom edge


class MosaicRubberBandSelector(QtCore.QObject):
    """Rubber-band (drag) selection and deselection for mosaic tiles."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        graphics_view: QtWidgets.QGraphicsView,
        selection_model: SelectionModel,
        visible_widgets_getter: Callable[[], list],
        drag_started: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = graphics_view
        self._selection_model = selection_model
        self._visible_widgets_getter = visible_widgets_getter
        self._drag_started = drag_started
        viewport = graphics_view.viewport()
        self._band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, viewport
        )
        self._press_pos: QtCore.QPoint | None = None
        self._origin_scene: QtCore.QPointF | None = None
        # Selection the drag adds to (Ctrl) or removes from (deselect drag),
        # taken before the press reaches the tile, since the press itself
        # changes the selection.
        self._base: list = []
        self._deselect = False
        self._dragging = False
        # Shown tiles by id -> grid position, taken at the press (they don't
        # change during a drag); and the ids under the band at the last move.
        self._order: dict[int, int] = {}
        self._shown: dict[int, object] = {}
        self._last_hit: frozenset[int] | None = None
        if viewport is not None:
            viewport.installEventFilter(self)

    @property
    def dragging(self) -> bool:
        return self._dragging

    def eventFilter(self, source, event) -> bool:  # type: ignore[override]
        kind = event.type()
        if (
            kind == QtCore.QEvent.Type.MouseButtonPress
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            modifiers = event.modifiers()
            if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                return False
            self._press_pos = event.position().toPoint()
            self._origin_scene = self._view.mapToScene(self._press_pos)
            shown = self._visible_widgets_getter()
            self._order = {id(w): i for i, w in enumerate(shown)}
            self._shown = {id(w): w for w in shown}
            self._last_hit = None
            pressed = next(iter(self._tiles_at(self._origin_scene)), None)
            self._deselect = pressed is not None and self._selection_model.is_selected(
                pressed
            )
            add = bool(modifiers & QtCore.Qt.KeyboardModifier.ControlModifier)
            self._base = self._selection_model.selected if add or self._deselect else []
            self._dragging = False
        elif kind == QtCore.QEvent.Type.MouseMove and self._press_pos is not None:
            if not event.buttons() & QtCore.Qt.MouseButton.LeftButton:
                self._finish()
                return False
            pos = event.position().toPoint()
            if not self._dragging:
                if (
                    pos - self._press_pos
                ).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                    return False
                self._dragging = True
                if self._drag_started is not None:
                    self._drag_started()
            self._update(pos)
            return True  # the drag owns the mouse now; tiles don't need the moves
        elif (
            kind == QtCore.QEvent.Type.MouseButtonRelease
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            # Not consumed: the scene still has to see the release to let go
            # of the tile that took the press.
            self._finish()
        return False

    def _update(self, pos: QtCore.QPoint) -> None:
        viewport = self._view.viewport()
        bar = self._view.verticalScrollBar()
        if bar is not None and viewport is not None:
            if pos.y() < 0:
                bar.setValue(bar.value() - DRAG_AUTOSCROLL_STEP)
            elif pos.y() > viewport.height():
                bar.setValue(bar.value() + DRAG_AUTOSCROLL_STEP)
        # The origin is kept in scene coordinates so it stays put while the
        # grid scrolls under it.
        band = QtCore.QRect(
            self._view.mapFromScene(self._origin_scene), pos
        ).normalized()
        if viewport is not None:
            self._band.setGeometry(band.intersected(viewport.rect()))
        self._band.show()
        scene_rect = self._view.mapToScene(band).boundingRect()
        hit = self._tiles_in(scene_rect)
        hit_ids = frozenset(id(w) for w in hit)
        if hit_ids == self._last_hit:
            return  # same tiles as the last move: nothing to change
        self._last_hit = hit_ids
        if self._deselect:
            gone = {id(w) for w in hit}
            self._selection_model.set_selection(
                [w for w in self._base if id(w) not in gone]
            )
        else:
            self._selection_model.set_selection(list(dict.fromkeys(self._base + hit)))

    def _tiles_in(self, scene_rect: QtCore.QRectF) -> list:
        """Shown tiles touching *scene_rect*, in grid order."""
        scene = self._view.scene()
        if scene is None:
            return []
        return self._shown_in_order(
            scene.items(
                scene_rect, QtCore.Qt.ItemSelectionMode.IntersectsItemBoundingRect
            )
        )

    def _tiles_at(self, scene_pos: QtCore.QPointF) -> list:
        """Shown tiles under *scene_pos*."""
        scene = self._view.scene()
        if scene is None:
            return []
        return self._shown_in_order(
            scene.items(
                scene_pos, QtCore.Qt.ItemSelectionMode.IntersectsItemBoundingRect
            )
        )

    def _shown_in_order(self, items: list) -> list:
        # The scene also holds the grid's container widget; keep shown tiles.
        hit = [self._shown[id(i)] for i in items if id(i) in self._shown]
        hit.sort(key=lambda w: self._order[id(w)])
        return hit

    def _finish(self) -> None:
        self._band.hide()
        self._press_pos = None
        self._origin_scene = None
        self._base = []  # no tile references kept past the drag
        self._order = {}
        self._shown = {}
        self._last_hit = None
        self._deselect = False
        self._dragging = False


__all__ = ["MosaicRubberBandSelector"]
