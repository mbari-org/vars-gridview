"""Graphics-scene manager for the ROI mosaic grid."""

from __future__ import annotations

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
    """Visibility toggles used to choose which widgets are rendered."""

    hide_labeled: bool = False
    hide_unlabeled: bool = False
    hide_training: bool = False
    hide_nontraining: bool = False


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
            rect_widget_width = max(int(round(rect_widget_width_f)), 1)
            rect_widget_height = max(int(round(rect_widget_height_f)), 1)

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
        visible_widgets = []
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
            visible_widgets.append(widget)
        return visible_widgets

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


__all__ = ["MosaicView", "MosaicRenderResult", "MosaicVisibilityFilters"]
