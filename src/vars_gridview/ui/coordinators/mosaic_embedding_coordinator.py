"""Coordinator for asynchronous embedding precompute in the mosaic."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
from PyQt6 import QtCore

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.lib.vision.embedding import Embedding
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class MosaicEmbeddingCoordinator(QtCore.QObject):
    """Own embedding-precompute worker lifecycle.

    Does not own any UI presentation itself; callers connect to
    :attr:`precompute_started`, :attr:`precompute_progress`, and
    :attr:`precompute_finished` to drive their own non-blocking progress
    display.
    """

    precompute_started = QtCore.pyqtSignal(int)  # total
    precompute_progress = QtCore.pyqtSignal(int, int)  # current, total
    precompute_finished = QtCore.pyqtSignal()
    # (generation, [(association_uuid, embedding), ...]) for each finished
    # chunk, emitted from the worker thread and delivered on the GUI thread.
    precompute_batch = QtCore.pyqtSignal(object)

    # Embeddings are handed over every CHUNK tiles rather than all at the
    # end: with thousands of tiles to compute, "Find similar" used to rank
    # only the stored ones until the very last tile was done, and one failed
    # request threw every computed vector away.
    CHUNK = 256

    def __init__(self, *, parent: QtCore.QObject) -> None:
        super().__init__(parent)

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
        self.precompute_batch.connect(self._deliver_batch)

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

        self._in_progress = True
        self.precompute_started.emit(len(targets))

        worker = Worker(
            self.compute_embeddings_payload,
            targets,
            embedding_model,
            generation,
            self.precompute_progress.emit,
            self.precompute_batch.emit,
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

    @QtCore.pyqtSlot(object)
    def _deliver_batch(self, payload: tuple[int, list[tuple[UUID, object]]]) -> None:
        # The receiver checks the generation, so a chunk of an old page is
        # ignored even if a newer request has replaced it.
        if self._latest_request is not None:
            self._latest_request[3](payload)

    @classmethod
    def compute_embeddings_payload(
        cls,
        rect_widgets: list[RectWidget],
        embedding_model: Embedding,
        generation: int,
        progress_callback: Callable[[int, int], None] | None = None,
        batch_callback: Callable[[tuple[int, list[tuple[UUID, object]]]], None]
        | None = None,
    ) -> tuple[int, list[tuple[UUID, object]]]:
        """Embed the tiles' images in chunks. Each finished chunk goes to
        *batch_callback* (when given) instead of into the returned payload,
        so results arrive as they're made. A failed chunk is logged and
        skipped; only "model not available" stops the run."""
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
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(f"Skipping ROI for embedding, failed to read: {exc}")
                continue
        if not roi_images:
            return generation, []

        total = len(roi_images)
        if progress_callback is not None:
            progress_callback(0, total)
        kept: list[tuple[UUID, object]] = []
        failed = 0
        for start in range(0, total, cls.CHUNK):
            chunk_uuids = uuids[start : start + cls.CHUNK]
            try:
                vectors = embedding_model.embed_many(
                    roi_images[start : start + cls.CHUNK]
                )
            except Exception as exc:
                if "not available" in str(exc).lower():
                    raise
                failed += len(chunk_uuids)
                LOGGER.warning(f"Embedding {len(chunk_uuids)} tiles failed: {exc}")
                vectors = []
            rows = list(zip(chunk_uuids, vectors, strict=True)) if vectors else []
            if rows:
                if batch_callback is not None:
                    batch_callback((generation, rows))
                else:
                    kept.extend(rows)
            if progress_callback is not None:
                progress_callback(min(start + cls.CHUNK, total), total)
        if failed:
            LOGGER.warning(
                f"{failed:,} of {total:,} tile embeddings could not be computed"
            )
        return generation, kept

    def _on_error(self, err: tuple, on_unavailable: Callable[[str], None]) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error("Embedding precompute failed: %s", message)
        if "not available" in message.lower():
            on_unavailable(message)

    @QtCore.pyqtSlot()
    def _on_finished(self) -> None:
        self._in_progress = False
        self.precompute_finished.emit()

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
