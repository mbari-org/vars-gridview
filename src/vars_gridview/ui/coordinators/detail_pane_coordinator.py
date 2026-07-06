"""Coordinate async detail-pane image loading and overlay rendering."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

import cv2
import numpy as np
from PyQt6 import QtCore

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.lib.annotation.box_handler import BoxHandler
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class DetailPaneCoordinator(QtCore.QObject):
    """Own detail pane async image loading and overlay placement."""

    def __init__(
        self,
        *,
        box_handler_getter: Callable[[], BoxHandler | None],
        selected_rect_getter: Callable[[], RectWidget | None],
    ) -> None:
        super().__init__()
        self._box_handler_getter = box_handler_getter
        self._selected_rect_getter = selected_rect_getter
        self._detail_request_generation = 0

    @staticmethod
    def rect_source_key(
        rect: RectWidget,
    ) -> tuple[Optional[str], Optional[int], float, float]:
        """Return a stable key for the source frame behind a rect widget."""
        return (
            rect.source_url,
            rect.elapsed_time_millis,
            rect.scale_x,
            rect.scale_y,
        )

    def show_rect_in_detail_async(
        self, rect: RectWidget, needs_autorange: bool
    ) -> None:
        """Load and display the detail image for *rect* off the UI thread."""
        self._detail_request_generation += 1
        generation = self._detail_request_generation

        worker = Worker(
            self._load_detail_image_worker,
            rect,
            generation,
            needs_autorange,
            rect.is_image,
            rect.scale_x,
            rect.scale_y,
        )
        worker.signals.result.connect(self._on_detail_worker_result)
        worker.signals.error.connect(
            lambda err: LOGGER.error(
                f"Error loading detail image for {rect.association.uuid}: {err[1]}"
            )
        )

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.error(
                "Global Qt thread pool is unavailable; cannot load detail image"
            )
            return
        pool.start(worker)

    def update_overlays_for_same_source(self, rect: RectWidget) -> bool:
        """Update detail overlays for a same-source selection without image reload."""
        box_handler = self._box_handler_getter()
        if box_handler is None:
            return False
        return box_handler.retarget_annotations_for_same_source(rect)

    @staticmethod
    def _load_detail_image_worker(
        rect: RectWidget,
        generation: int,
        needs_autorange: bool,
        is_image: bool,
        scale_x: float,
        scale_y: float,
    ):
        image = rect.get_image()
        if image is None:
            LOGGER.error(f"Could not load detail image from {rect.source_url}")
            return (
                generation,
                needs_autorange,
                DetailPaneCoordinator._placeholder_image(),
            )

        if not is_image and (scale_x != 1.0 or scale_y != 1.0):
            image = cv2.resize(
                image,
                None,
                fx=scale_x,
                fy=scale_y,
                interpolation=cv2.INTER_CUBIC,
            )

        if image is None:
            return (
                generation,
                needs_autorange,
                DetailPaneCoordinator._placeholder_image(),
            )

        return generation, needs_autorange, image

    @staticmethod
    def _placeholder_image() -> np.ndarray:
        """Return a visible fallback image for detail-pane load failures."""
        placeholder = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            "Image unavailable",
            (40, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            2.0,
            (220, 220, 220),
            3,
            cv2.LINE_AA,
        )
        return placeholder

    @QtCore.pyqtSlot(object)
    def _on_detail_worker_result(self, payload) -> None:
        generation, needs_autorange, rect_full_image = payload
        rect = self._selected_rect_getter()
        if rect is None:
            return
        self._on_rect_detail_ready(rect, generation, needs_autorange, rect_full_image)

    def _on_rect_detail_ready(
        self,
        rect: RectWidget,
        generation: int,
        needs_autorange: bool,
        rect_full_image,
    ) -> None:
        """Apply async detail-image result to the ROI detail view if still current."""
        if generation != self._detail_request_generation:
            return
        if self._selected_rect_getter() is not rect:
            return
        source_image_height, source_image_width = rect_full_image.shape[:2]
        rect.set_source_image_dimensions(source_image_width, source_image_height)

        box_handler = self._box_handler_getter()
        if box_handler is None:
            return

        rgb_image = np.ascontiguousarray(
            cv2.cvtColor(rect_full_image, cv2.COLOR_BGR2RGB)
        )
        box_handler.roi_detail.setImage(rgb_image)
        if needs_autorange:
            box_handler.view_box.autoRange()

        box_handler.add_annotation(
            rect.localization_index,
            rect,
            image_height=source_image_height,
            image_width=source_image_width,
        )
