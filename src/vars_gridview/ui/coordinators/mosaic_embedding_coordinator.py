"""Coordinator for asynchronous embedding precompute in the mosaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable
from uuid import UUID

import numpy as np
from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.lib.vision.embedding import Embedding
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class MosaicEmbeddingCoordinator(QtCore.QObject):
    """Own embedding-precompute worker lifecycle and progress UI."""

    precompute_progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._dialog: QtWidgets.QProgressDialog | None = None

        self._in_progress = False
        self._pending = False
        self._latest_request: (
            tuple[
                list[RectWidget],
                Embedding | None,
                int,
                Callable[[tuple[int, list[tuple[UUID, object]]]], None],
                Callable[[str], None],
            ]
            | None
        ) = None

        self.precompute_progress.connect(self._on_progress)

    def on_model_changed(self, *, model_changed: bool, has_model: bool) -> None:
        """Track whether an in-flight precompute should be restarted."""
        if model_changed and self._in_progress:
            self._pending = has_model
        if not has_model:
            self._pending = False

    def request_precompute(
        self,
        *,
        rect_widgets: list[RectWidget],
        embedding_model: Embedding | None,
        generation: int,
        on_result: Callable[[tuple[int, list[tuple[UUID, object]]]], None],
        on_unavailable: Callable[[str], None],
    ) -> None:
        """Start precompute, or queue a restart if one is already running."""
        self._latest_request = (
            rect_widgets,
            embedding_model,
            generation,
            on_result,
            on_unavailable,
        )

        if embedding_model is None or not rect_widgets:
            return

        targets = [rw for rw in rect_widgets if not rw.has_cached_embedding]
        if not targets:
            return

        if self._in_progress:
            self._pending = True
            return

        self._dialog = QtWidgets.QProgressDialog(
            "Precomputing embeddings...",
            None,
            0,
            len(targets),
            self._dialog_parent,
        )
        self._dialog.setWindowTitle("Embeddings")
        self._dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.setValue(0)
        self._dialog.show()

        self._in_progress = True
        worker = Worker(
            self.compute_embeddings_payload,
            targets,
            embedding_model,
            generation,
            self.precompute_progress.emit,
        )
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(lambda err: self._on_error(err, on_unavailable))
        worker.signals.finished.connect(self._on_finished)

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.error("Global thread pool unavailable; cannot precompute embeddings")
            self._on_finished()
            return
        pool.start(worker)

    @staticmethod
    def compute_embeddings_payload(
        rect_widgets: list[RectWidget],
        embedding_model: Embedding,
        generation: int,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[tuple[UUID, object]]]:
        uuids: list[UUID] = []
        roi_images: list[np.ndarray] = []
        for rect_widget in rect_widgets:
            try:
                if not rect_widget.roi_loaded:
                    continue
                roi = rect_widget.roi
                if roi is None:
                    continue
                uuids.append(rect_widget.association_uuid)
                roi_images.append(roi[:, :, ::-1])
            except Exception:
                continue

        if not roi_images:
            return generation, []

        embeddings = embedding_model.embed_many(
            roi_images,
            progress_callback=progress_callback,
        )
        return generation, list(zip(uuids, embeddings))

    def _on_error(self, err: tuple, on_unavailable: Callable[[str], None]) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error("Embedding precompute failed: %s", message)
        if "not available" in message.lower():
            on_unavailable(message)

    @QtCore.pyqtSlot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        if self._dialog is None:
            return
        self._dialog.setMaximum(max(0, total))
        self._dialog.setValue(max(0, min(current, total)))

    @QtCore.pyqtSlot()
    def _on_finished(self) -> None:
        self._in_progress = False
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None

        if not self._pending or self._latest_request is None:
            return

        self._pending = False
        (
            rect_widgets,
            embedding_model,
            generation,
            on_result,
            on_unavailable,
        ) = self._latest_request
        if embedding_model is None:
            return

        self.request_precompute(
            rect_widgets=rect_widgets,
            embedding_model=embedding_model,
            generation=generation,
            on_result=on_result,
            on_unavailable=on_unavailable,
        )


__all__ = ["MosaicEmbeddingCoordinator"]
