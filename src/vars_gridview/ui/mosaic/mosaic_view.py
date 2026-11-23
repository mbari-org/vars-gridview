"""Graphics-scene manager for the ROI mosaic grid."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.style import UiDimensions


@dataclass
class MosaicRenderResult:
    """Summary of a mosaic render pass."""

    columns: int
    rendered_count: int


@dataclass
class MosaicVisibilityFilters:
    """Visibility toggles used to choose which widgets are rendered.

    ``label`` keeps only tiles showing that label (``None`` = all labels).
    ``min_confidence``/``max_confidence`` keep only tiles whose association
    ``confidence`` is in the inclusive range; while the range is narrowed
    (anything but 0-1), tiles with no confidence at all -- typically
    human-drawn boxes -- are hidden too.
    """

    hide_labeled: bool = False
    hide_unlabeled: bool = False
    hide_training: bool = False
    hide_nontraining: bool = False
    label: str | None = None
    min_confidence: float = 0.0
    max_confidence: float = 1.0

    @property
    def confidence_active(self) -> bool:
        return self.min_confidence > 0.0 or self.max_confidence < 1.0


def association_confidence(association: object) -> float | None:
    """The association's ``confidence`` as a float, or None if absent/invalid."""
    data = getattr(association, "data", None)
    if not isinstance(data, dict):
        return None
    value = data.get("confidence")
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


@dataclass
class VisibilityResult:
    """Tiles to show, plus what the confidence range alone hid, per label."""

    visible: list
    hidden_by_confidence: dict[str, int]


class MosaicView:
    """Owns QGraphicsScene/QGraphicsWidget layout for mosaic tiles."""

    def __init__(self, graphics_view: QtWidgets.QGraphicsView) -> None:
        self._graphics_view = graphics_view
        self._graphics_scene = QtWidgets.QGraphicsScene()
        self._graphics_widget = QtWidgets.QGraphicsWidget()
        self._layout = QtWidgets.QGraphicsGridLayout()
        self._last_visible_signature: tuple[int, ...] = ()
        self._last_columns: int = -1
        self._last_widget_size: tuple[int, int] = (-1, -1)
        self._init_graphics()

    @property
    def graphics_view(self) -> QtWidgets.QGraphicsView:
        return self._graphics_view

    def _init_graphics(self) -> None:
        self._graphics_view.setScene(self._graphics_scene)
        self._graphics_scene.addItem(self._graphics_widget)
        self._layout.setContentsMargins(*UiDimensions.MOSAIC_LAYOUT_MARGINS)
        self._layout.setHorizontalSpacing(UiDimensions.MOSAIC_LAYOUT_SPACING)
        self._layout.setVerticalSpacing(UiDimensions.MOSAIC_LAYOUT_SPACING)
        self._graphics_widget.setLayout(self._layout)

    def _clear_graphics_layout(self) -> None:
        while self._layout.count() > 0:
            self._layout.removeAt(0)

    def clear(self, rect_widgets: list) -> None:
        """Hide all widgets and clear scene layout."""
        for rect_widget in rect_widgets:
            rect_widget.hide()

        self._clear_graphics_layout()
        self._graphics_scene.setSceneRect(QtCore.QRectF())
        self._last_visible_signature = ()
        self._last_columns = -1
        self._last_widget_size = (-1, -1)

    def dispose(self, rect_widgets: list) -> None:
        """Take tiles out of the scene for good and let Qt delete them.

        ``QGraphicsGridLayout.removeAt`` only unlinks a tile from the layout;
        it stays in the scene as a hidden child of the grid widget, holding
        its pixmap and crop. Without this every query or page change leaked
        the previous page's tiles.
        """
        if not rect_widgets:
            return
        self._graphics_view.setUpdatesEnabled(False)
        try:
            gone = {id(w) for w in rect_widgets}
            for idx in range(self._layout.count() - 1, -1, -1):
                item = self._layout.itemAt(idx)
                if id(item) in gone:
                    self._layout.removeAt(idx)
            for rect_widget in rect_widgets:
                rect_widget.hide()
                if rect_widget.scene() is self._graphics_scene:
                    self._graphics_scene.removeItem(rect_widget)
                rect_widget.deleteLater()
        finally:
            self._graphics_view.setUpdatesEnabled(True)
        self._last_visible_signature = ()

    def render(
        self,
        *,
        all_widgets: list,
        visible_widgets: list,
    ) -> MosaicRenderResult:
        """Render `visible_widgets` in a responsive grid."""
        left, _top, right, _bottom = self._layout.getContentsMargins()
        left_i = self._coerce_margin(left)
        right_i = self._coerce_margin(right)
        viewport = self._graphics_view.viewport()
        viewport_width = viewport.width() if viewport is not None else 0
        width = viewport_width - left_i - right_i

        if all_widgets:
            rect_widget_width_f = all_widgets[0].boundingRect().width()
            rect_widget_height_f = all_widgets[0].boundingRect().height()

            # Defensive guard: stale/invalid geometry can transiently report zero.
            rect_widget_width = max(round(rect_widget_width_f), 1)
            rect_widget_height = max(round(rect_widget_height_f), 1)

            columns = max(int(width / rect_widget_width), 1)
        else:
            rect_widget_width = 0
            rect_widget_height = 0
            columns = 1

        visible_signature = tuple(id(widget) for widget in visible_widgets)
        if (
            visible_signature == self._last_visible_signature
            and columns == self._last_columns
            and (rect_widget_width, rect_widget_height) == self._last_widget_size
        ):
            return MosaicRenderResult(
                columns=columns, rendered_count=len(visible_widgets)
            )

        self._graphics_view.setUpdatesEnabled(False)
        try:
            self._clear_graphics_layout()

            visible_ids = set(visible_signature)
            for rw in all_widgets:
                if id(rw) not in visible_ids:
                    rw.hide()

            for idx, rect_widget in enumerate(visible_widgets):
                row = idx // columns
                col = idx % columns
                self._layout.addItem(rect_widget, row, col)
                rect_widget.show()

            rows = (len(visible_widgets) + columns - 1) // columns
            self._graphics_widget.resize(
                columns * rect_widget_width,
                rows * rect_widget_height,
            )
            self._graphics_scene.setSceneRect(self._graphics_widget.boundingRect())
            # Lay out now, so tiles have scene positions straight away (the
            # on-screen-first loader asks which tiles are in view).
            self._layout.activate()
        finally:
            self._graphics_view.setUpdatesEnabled(True)

        self._last_visible_signature = visible_signature
        self._last_columns = columns
        self._last_widget_size = (rect_widget_width, rect_widget_height)

        return MosaicRenderResult(columns=columns, rendered_count=len(visible_widgets))

    def select_visible_widgets(
        self,
        *,
        all_widgets: list,
        filters: MosaicVisibilityFilters,
    ) -> list:
        """Return widgets that pass current visibility filter toggles."""
        return self.apply_filters(all_widgets=all_widgets, filters=filters).visible

    @staticmethod
    def apply_filters(
        *,
        all_widgets: list,
        filters: MosaicVisibilityFilters,
    ) -> VisibilityResult:
        """Visible widgets, and per label how many passed every other filter
        but fell outside the confidence range (so the user can see what the
        range is hiding)."""
        visible_widgets = []
        hidden: dict[str, int] = {}
        lo, hi = filters.min_confidence, filters.max_confidence
        for widget in all_widgets:
            association = getattr(widget, "association", None)
            if association is None:
                continue
            if filters.hide_labeled and getattr(association, "verified", False):
                continue
            if filters.hide_unlabeled and not getattr(association, "verified", False):
                continue
            if filters.hide_training and getattr(association, "is_training", False):
                continue
            if filters.hide_nontraining and not getattr(
                association, "is_training", False
            ):
                continue
            label = getattr(association, "text_label", None)
            if filters.label is not None and label != filters.label:
                continue
            if filters.confidence_active:
                confidence = association_confidence(association)
                if confidence is None or not (lo <= confidence <= hi):
                    key = str(label)
                    hidden[key] = hidden.get(key, 0) + 1
                    continue
            visible_widgets.append(widget)
        return VisibilityResult(visible=visible_widgets, hidden_by_confidence=hidden)

    def widgets_near_viewport(
        self, visible_widgets: list, margin_screens: float = 1.0
    ) -> list:
        """Laid-out widgets on screen first, then those within *margin_screens*
        screen heights above/below, nearest first."""
        viewport = self._graphics_view.viewport()
        if viewport is None or not visible_widgets:
            return []
        view_rect = self._graphics_view.mapToScene(viewport.rect()).boundingRect()
        margin = view_rect.height() * margin_screens
        top, bottom = view_rect.top(), view_rect.bottom()
        near = []
        for widget in visible_widgets:
            rect = widget.sceneBoundingRect()
            if rect.bottom() < top - margin or rect.top() > bottom + margin:
                continue
            if rect.bottom() >= top and rect.top() <= bottom:
                distance = 0.0
            else:
                distance = min(abs(rect.top() - bottom), abs(top - rect.bottom()))
            near.append((distance, widget))
        near.sort(key=lambda pair: pair[0])
        return [widget for _distance, widget in near]

    def ensure_widget_visible_if_needed(self, rect_widget: object) -> None:
        """Scroll view only when `rect_widget` is outside current viewport."""
        viewport = self._graphics_view.viewport()
        if viewport is None:
            return

        item_rect_scene = rect_widget.sceneBoundingRect()
        item_rect_view = self._graphics_view.mapFromScene(
            item_rect_scene
        ).boundingRect()
        viewport_rect = viewport.rect()
        if viewport_rect.contains(item_rect_view):
            return

        self._graphics_view.ensureVisible(item_rect_scene, 8, 8)

    def visible_widgets_in_range(
        self,
        *,
        all_widgets: list,
        begin_index: int,
        end_index: int,
    ) -> list:
        """Return currently visible widgets within an inclusive index range."""
        if begin_index < 0 or end_index < begin_index:
            return []
        max_index = len(all_widgets) - 1
        if max_index < 0:
            return []
        bounded_begin = min(begin_index, max_index)
        bounded_end = min(end_index, max_index)

        visible: list = []
        for idx in range(bounded_begin, bounded_end + 1):
            widget = all_widgets[idx]
            if widget.isVisible():
                visible.append(widget)
        return visible

    @staticmethod
    def compute_relative_index(
        *,
        current_index: int,
        key: QtCore.Qt.Key,
        columns: int,
        total_items: int,
    ) -> int | None:
        """Compute next selection index for arrow-key navigation."""
        if current_index < 0 or current_index >= total_items:
            return None
        if columns <= 0:
            return None

        if key == QtCore.Qt.Key.Key_Left:
            next_index = current_index - 1
        elif key == QtCore.Qt.Key.Key_Right:
            next_index = current_index + 1
        elif key == QtCore.Qt.Key.Key_Up:
            next_index = current_index - columns
        elif key == QtCore.Qt.Key.Key_Down:
            next_index = current_index + columns
        else:
            return None

        if 0 <= next_index < total_items:
            return next_index
        return None

    @staticmethod
    def _coerce_margin(value: object) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        return 0


__all__ = ["MosaicRenderResult", "MosaicView", "MosaicVisibilityFilters"]
