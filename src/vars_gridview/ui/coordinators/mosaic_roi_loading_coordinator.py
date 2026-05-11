"""Coordinator for asynchronous ROI tile loading lifecycle in the mosaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from PyQt6 import QtCore, QtWidgets


if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class MosaicRoiLoadingCoordinator(QtCore.QObject):
    """Own ROI loading queueing, progress dialog, and completion callback."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget | None,
        max_concurrency: int = 4,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._max_concurrency = max(1, int(max_concurrency))

        self._generation = 0
        self._total = 0
        self._done = 0
        self._pending: list[RectWidget] = []
        self._inflight = 0
        self._dialog: QtWidgets.QProgressDialog | None = None
        self._on_complete: Callable[[], None] | None = None

    def cancel_pending(self) -> None:
        """Invalidate in-flight ROI refreshes and close progress UI."""
        self._generation += 1
        self._total = 0
        self._done = 0
        self._pending = []
        self._inflight = 0
        self._on_complete = None
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None

    def start_loading(
        self,
        *,
        rect_widgets: list[RectWidget],
        on_complete: Callable[[], None],
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

        self._dialog = QtWidgets.QProgressDialog(
            "Loading ROI images...",
            None,
            0,
            self._total,
            self._dialog_parent,
        )
        self._dialog.setWindowTitle("Loading")
        self._dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setValue(0)
        self._dialog.show()

        self._pump(generation)

    def _pump(self, generation: int) -> None:
        while (
            generation == self._generation
            and self._inflight < self._max_concurrency
            and self._pending
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

        dialog = self._dialog
        if dialog is not None:
            dialog.setValue(self._done)

        self._pump(self._generation)

        if self._done >= self._total:
            if self._dialog is dialog and dialog is not None:
                dialog.close()
                self._dialog = None
            callback = self._on_complete
            self._on_complete = None
            if callback is not None:
                callback()


__all__ = ["MosaicRoiLoadingCoordinator"]
