"""Coordinate async detail-pane image loading and overlay rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PyQt6 import QtCore

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.lib.vision.display_adjust import brightness_contrast

if TYPE_CHECKING:
    from vars_gridview.lib.annotation.box_handler import BoxHandler
    from vars_gridview.ui.mosaic.rect_widget import DisplayContext, RectWidget


class DetailPaneCoordinator(QtCore.QObject):
    """Own detail pane async image loading and overlay placement."""

    def __init__(
        self,
        *,
        box_handler_getter: Callable[[], BoxHandler | None],
        selected_rect_getter: Callable[[], RectWidget | None],
        display_context_getter: Callable[[], DisplayContext | None] | None = None,
        frame_loaded_callback: Callable[[RectWidget, np.ndarray], None] | None = None,
    ) -> None:
        super().__init__()
        self._box_handler_getter = box_handler_getter
        self._selected_rect_getter = selected_rect_getter
        self._display_context_getter = display_context_getter or (lambda: None)
        # Told about every real (not placeholder) frame shown, e.g. so tiles
        # from that frame can use its whole-frame colour correction.
        self._frame_loaded_callback = frame_loaded_callback
        self._detail_request_generation = 0
        self._current_detail_image: np.ndarray | None = None
        # The frame as loaded (BGR, unadjusted), to redraw when the view
        # adjustments change.
        self._raw_detail_image: np.ndarray | None = None
        self._raw_detail_rect: RectWidget | None = None

    def _displayed(self, bgr: np.ndarray, rect: RectWidget | None) -> np.ndarray:
        """*bgr* with the current view adjustments that make sense on a whole
        frame: colour correction (with the frame's own measurement) and
        brightness/contrast. Fringes and sharpening are tile-scale and left
        out here."""
        context = self._display_context_getter()
        if context is None or rect is None:
            return bgr
        adjustment = context.adjustment
        if adjustment.colour_correct:
            try:
                bgr = context.corrector.apply(bgr, rect.frame_key)
            except Exception as exc:  # noqa: BLE001 -- show the original instead
                LOGGER.error(f"Colour correction failed for the image view: {exc}")
        return brightness_contrast(bgr, adjustment.brightness, adjustment.contrast)

    def _set_detail_image(self, box_handler: BoxHandler, bgr: np.ndarray) -> None:
        rgb_image = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        # pyqtgraph's ImageItem wraps this buffer via a raw pointer
        # (pyqtgraph.functions.ndarray_to_qimage) and depends on a dynamic
        # `qimage.data = arr` attribute to keep it alive Qt-side. Hold our own
        # strong reference too so that mechanism failing (or a repaint
        # queued against a since-replaced image) can't leave Qt painting from
        # freed memory.
        self._current_detail_image = rgb_image
        box_handler.roi_detail.setImage(rgb_image)

    def refresh_display(self) -> None:
        """Redraw the shown frame after the view adjustments changed."""
        box_handler = self._box_handler_getter()
        if box_handler is None or self._raw_detail_image is None:
            return
        selected = self._selected_rect_getter()
        # Another tile from the same frame reuses the loaded image.
        if selected is None or self._raw_detail_rect is None:
            return
        if selected.frame_key != self._raw_detail_rect.frame_key:
            return
        self._set_detail_image(
            box_handler, self._displayed(self._raw_detail_image, self._raw_detail_rect)
        )

    @staticmethod
    def rect_source_key(
        rect: RectWidget,
    ) -> tuple[str | None, int | None, float, float]:
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

        def should_cancel() -> bool:
            return generation != self._detail_request_generation

        worker = Worker(
            self._load_detail_image_worker,
            rect,
            generation,
            needs_autorange,
            rect.is_image,
            rect.scale_x,
            rect.scale_y,
            should_cancel,
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
        should_cancel: Callable[[], bool],
    ):
        image = rect.get_image(should_cancel=should_cancel)
        if image is None:
            if should_cancel():
                LOGGER.debug(
                    f"Detail image load for {rect.source_url} superseded before completion"
                )
            else:
                LOGGER.error(f"Could not load detail image from {rect.source_url}")
            return (
                generation,
                needs_autorange,
                DetailPaneCoordinator._placeholder_image(),
                True,
            )

        # RectWidget.get_image has already scaled a proxy frame up to the
        # source resolution the boxes are in; scaling it again here put the
        # boxes in the wrong place on proxy-backed video.
        return generation, needs_autorange, image, False

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
        generation, needs_autorange, rect_full_image, is_placeholder = payload
        rect = self._selected_rect_getter()
        if rect is None:
            return
        self._on_rect_detail_ready(
            rect, generation, needs_autorange, rect_full_image, is_placeholder
        )

    def _on_rect_detail_ready(
        self,
        rect: RectWidget,
        generation: int,
        needs_autorange: bool,
        rect_full_image,
        is_placeholder: bool = False,
    ) -> None:
        """Apply async detail-image result to the ROI detail view if still current."""
        if generation != self._detail_request_generation:
            return
        if self._selected_rect_getter() is not rect:
            return
        source_image_height, source_image_width = rect_full_image.shape[:2]
        if not is_placeholder:
            # Not from the "Image unavailable" placeholder: its 1280x720 would
            # become the box bounds, and dragging a box on a 4K frame would
            # clamp it and save wrong coordinates.
            rect.set_source_image_dimensions(source_image_width, source_image_height)

        box_handler = self._box_handler_getter()
        if box_handler is None:
            return

        if is_placeholder:
            self._raw_detail_image = None
            self._raw_detail_rect = None
            self._set_detail_image(box_handler, rect_full_image)
        else:
            self._raw_detail_image = rect_full_image
            self._raw_detail_rect = rect
            if self._frame_loaded_callback is not None:
                try:
                    self._frame_loaded_callback(rect, rect_full_image)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(f"Frame-loaded callback failed: {exc}")
            self._set_detail_image(box_handler, self._displayed(rect_full_image, rect))
        if needs_autorange:
            box_handler.view_box.autoRange()

        if is_placeholder:
            return  # no editable boxes over a missing image

        box_handler.add_annotation(
            rect.localization_index,
            rect,
            image_height=source_image_height,
            image_width=source_image_width,
        )
