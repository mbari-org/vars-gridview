"""Coordinator for asynchronous similarity sorting in the mosaic."""

from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING, Callable, Protocol, cast

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class _SimilarityRect(Protocol):
    text_label: str

    def embedding_distance(self, other: object) -> float: ...


class MosaicSimilarityCoordinator(QtCore.QObject):
    """Own similarity-sort worker lifecycle and progress UI."""

    sort_progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget | None,
        rect_widgets_getter: Callable[[], list[RectWidget]],
        apply_sorted_indices: Callable[[list[int]], None],
        sort_unavailable_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._rect_widgets_getter = rect_widgets_getter
        self._apply_sorted_indices = apply_sorted_indices
        self._sort_unavailable_callback = sort_unavailable_callback
        self._dialog: QtWidgets.QProgressDialog | None = None

        self.sort_progress.connect(self._on_progress)

    def start(self, clicked_rect: object, same_class_only: bool) -> None:
        """Compute and apply similarity sort order asynchronously."""
        rect_widgets = list(self._rect_widgets_getter())
        if not rect_widgets:
            return

        self._dialog = QtWidgets.QProgressDialog(
            "Computing similarity sort...",
            None,
            0,
            len(rect_widgets),
            self._dialog_parent,
        )
        self._dialog.setWindowTitle("Sorting")
        self._dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setValue(0)
        self._dialog.show()

        worker = Worker(
            self.compute_similarity_sort_order,
            cast(list[_SimilarityRect], rect_widgets),
            cast(_SimilarityRect, clicked_rect),
            same_class_only,
            self.sort_progress.emit,
        )
        worker.signals.result.connect(self._on_ready)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._on_finished)

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.error("Global thread pool unavailable; cannot run similarity sort")
            self._on_finished()
            return
        pool.start(worker)

    @staticmethod
    def compute_similarity_sort_order(
        rect_widgets: list[_SimilarityRect],
        clicked_rect: _SimilarityRect,
        same_class_only: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[int]:
        total = len(rect_widgets)
        if progress_callback is not None:
            progress_callback(0, total)

        scored: list[tuple[float, int]] = []
        for idx, rect_widget in enumerate(rect_widgets, start=1):
            if same_class_only and clicked_rect.text_label != rect_widget.text_label:
                distance = inf
            else:
                try:
                    distance = clicked_rect.embedding_distance(rect_widget)
                except Exception:
                    distance = inf

            scored.append((distance, idx - 1))
            if progress_callback is not None and (idx == total or idx % 32 == 0):
                progress_callback(idx, total)

        scored.sort(key=lambda pair: pair[0])
        return [idx for _distance, idx in scored]

    @QtCore.pyqtSlot(object)
    def _on_ready(self, sorted_indices: object) -> None:
        if isinstance(sorted_indices, list) and all(
            isinstance(idx, int) for idx in sorted_indices
        ):
            self._apply_sorted_indices(cast(list[int], sorted_indices))

    @QtCore.pyqtSlot(tuple)
    def _on_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error("Similarity sort failed: %s", message)
        if (
            "not available" in message.lower()
            and self._sort_unavailable_callback is not None
        ):
            self._sort_unavailable_callback(message)

    @QtCore.pyqtSlot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        if self._dialog is None:
            return
        self._dialog.setMaximum(max(0, total))
        self._dialog.setValue(max(0, min(current, total)))

    @QtCore.pyqtSlot()
    def _on_finished(self) -> None:
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None


__all__ = ["MosaicSimilarityCoordinator"]
