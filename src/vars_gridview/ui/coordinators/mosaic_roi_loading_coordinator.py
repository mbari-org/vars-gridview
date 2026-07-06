"""Coordinator for asynchronous ROI tile loading lifecycle in the mosaic."""

from __future__ import annotations

from threading import Event
from typing import TYPE_CHECKING, Callable, cast

from PyQt6 import QtCore


if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class MosaicRoiLoadingCoordinator(QtCore.QObject):
    """Own ROI loading queueing and completion callback.

    Does not own any UI presentation itself; callers connect to
    :attr:`progress` to drive their own shared progress display.
    """

    progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        max_concurrency: int = 4,
    ) -> None:
        super().__init__(parent)
        self._max_concurrency = max(1, int(max_concurrency))

        self._generation = 0
        self._total = 0
        self._done = 0
        self._pending: list[RectWidget] = []
        self._inflight = 0
        self._on_complete: Callable[[], None] | None = None
        self._cancel_event: Event | None = None

    def cancel_pending(self) -> None:
        """Invalidate in-flight ROI refreshes."""
        self._generation += 1
        self._total = 0
        self._done = 0
        self._pending = []
        self._inflight = 0
        self._on_complete = None
        self._cancel_event = None

    def start_loading(
        self,
        *,
        rect_widgets: list[RectWidget],
        on_complete: Callable[[], None],
        cancel_event: Event,
    ) -> None:
        """Start batched async ROI loading for the given widgets."""
        if not rect_widgets:
            return

        self.cancel_pending()
        self._generation += 1
        generation = self._generation

        self._total = len(rect_widgets)
        self._done = 0
        self._pending = list(rect_widgets)
        self._inflight = 0
        self._on_complete = on_complete
        self._cancel_event = cancel_event

        self.progress.emit(self._done, self._total)
        self._pump(generation)

    def _pump(self, generation: int) -> None:
        while (
            generation == self._generation
            and self._inflight < self._max_concurrency
            and self._pending
            and not (self._cancel_event is not None and self._cancel_event.is_set())
        ):
            rect_widget = self._pending.pop(0)
            rect_widget.assign_roi_batch_generation(generation)
            rect_widget.roiRefreshed.connect(self._on_rect_roi_refreshed)
            self._inflight += 1
            rect_widget.request_roi_refresh()

    @QtCore.pyqtSlot(object)
    def _on_rect_roi_refreshed(self, rect_widget: object) -> None:
        rw = cast("RectWidget", rect_widget)
        try:
            rw.roiRefreshed.disconnect(self._on_rect_roi_refreshed)
        except Exception:
            pass

        if rw.roi_batch_generation != self._generation:
            return

        self._inflight = max(0, self._inflight - 1)
        self._done += 1
        self.progress.emit(self._done, self._total)

        self._pump(self._generation)

        cancelled = self._cancel_event is not None and self._cancel_event.is_set()
        if cancelled:
            if self._inflight == 0:
                self._on_complete = None
            return

        if self._done >= self._total:
            callback = self._on_complete
            self._on_complete = None
            if callback is not None:
                callback()


__all__ = ["MosaicRoiLoadingCoordinator"]
