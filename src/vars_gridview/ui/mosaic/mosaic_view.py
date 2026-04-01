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

    @staticmethod
    def _coerce_margin(value: object) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        return 0


__all__ = ["MosaicView", "MosaicRenderResult"]
