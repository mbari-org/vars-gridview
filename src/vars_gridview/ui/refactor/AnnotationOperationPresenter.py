"""Presentation logic for annotation operation lifecycle callbacks."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from PyQt6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from vars_gridview.lib.box_handler import BoxHandler
    from vars_gridview.ui.ImageMosaic import ImageMosaic
    from vars_gridview.ui.refactor.AnnotationActionCoordinator import (
        AnnotationActionCoordinator,
    )


class AnnotationOperationPresenter:
    """Render UI updates for annotation operation start/finish/failure."""

    def __init__(
        self,
        *,
        parent: QtWidgets.QWidget,
        image_mosaic: ImageMosaic,
        roi_graphics_view: QtWidgets.QGraphicsView,
        clear_detail_panels_callback: Callable[[], None],
        status_update_callback: Callable[[dict[str, str]], None],
        box_handler_getter: Callable[[], BoxHandler | None],
        action_state: AnnotationActionCoordinator,
    ) -> None:
        self._parent = parent
        self._image_mosaic = image_mosaic
        self._roi_graphics_view = roi_graphics_view
        self._clear_detail_panels_callback = clear_detail_panels_callback
        self._status_update_callback = status_update_callback
        self._box_handler_getter = box_handler_getter
        self._action_state = action_state

    def on_started(self, description: str) -> None:
        self._status_update_callback({"Status": description})

    def on_finished(self) -> None:
        if self._action_state.pending_action == "delete":
            scroll_bar = self._roi_graphics_view.verticalScrollBar()
            scroll_position = scroll_bar.value() if scroll_bar is not None else None

            self._image_mosaic.remove_rect_widgets(
                self._action_state.consume_pending_deleted_rects()
            )

            box_handler = self._box_handler_getter()
            if box_handler is not None:
                box_handler.roi_detail.clear()
                box_handler.clear()

            self._clear_detail_panels_callback()
            if scroll_bar is not None and scroll_position is not None:
                QtCore.QTimer.singleShot(
                    50, lambda: scroll_bar.setValue(scroll_position)
                )
        else:
            for rect in self._image_mosaic.get_all_rect_widgets():
                rect.text_label = rect.association.text_label
                rect.is_selected = False
                rect.update()

            box_handler = self._box_handler_getter()
            if box_handler is not None:
                box_handler.update_labels()

            self._image_mosaic.render_mosaic()

        self._status_update_callback({"Status": "Ready"})
        self._action_state.clear_pending()

    def on_failed(self, message: str) -> None:
        self._status_update_callback({"Status": "Action failed"})
        QtWidgets.QMessageBox.critical(self._parent, "Operation Failed", message)
        self._action_state.clear_pending()
