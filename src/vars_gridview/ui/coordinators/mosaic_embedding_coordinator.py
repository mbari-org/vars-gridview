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
    # (generation, model_name, [(association_uuid, embedding, box), ...]) for
    # each finished chunk, emitted from the worker thread and delivered on
    # the GUI thread. *box* is the box the embedded image was cropped from.
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
                list[RectWidget] | Callable[[], list[RectWidget]],
                Embedding | None,
                int,
                Callable[[tuple], None],
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
        rect_widgets: list[RectWidget] | Callable[[], list[RectWidget]],
        embedding_model: Embedding | None,
        generation: int,
        on_result: Callable[[tuple], None],
        on_unavailable: Callable[[str], None],
    ) -> None:
        """Start precompute, or queue a restart if one is already running.

        *rect_widgets* may be a getter: a queued restart then reads the tiles
        as they are when it runs, not a list kept from the request (which,
        after a delete, still held the deleted tiles)."""
        self._latest_request = (
            rect_widgets,
            embedding_model,
            generation,
            on_result,
            on_unavailable,
        )
        if callable(rect_widgets):
            rect_widgets = rect_widgets()

        if embedding_model is None or not rect_widgets:
            return

        targets = [rw for rw in rect_widgets if not rw.has_cached_embedding]
        if not targets:
            return

        if self._in_progress:
            self._pending = True
            return

        # Snapshot on the GUI thread: the worker gets plain data, never the
        # tiles (whose image and box the GUI thread may replace meanwhile).
        items = self.snapshot(targets)
        if not items:
            return
        self._in_progress = True
        self.precompute_started.emit(len(items))

        worker = Worker(
            self.compute_embeddings_payload,
            items,
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
    def _deliver_batch(self, payload: tuple) -> None:
        # The receiver checks the generation, so a chunk of an old page is
        # ignored even if a newer request has replaced it.
        if self._latest_request is not None:
            self._latest_request[3](payload)

    @staticmethod
    def snapshot(
        rect_widgets: list[RectWidget],
    ) -> list[tuple[UUID, np.ndarray, tuple]]:
        """``(association_uuid, RGB image, box it was cropped from)`` for each
        tile whose image has loaded."""
        items = []
        for rect_widget in rect_widgets:
            try:
                if not rect_widget.roi_loaded or rect_widget.roi is None:
                    continue
                items.append(
                    (
                        rect_widget.association_uuid,
                        rect_widget.roi[:, :, ::-1],
                        rect_widget.roi_box,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(f"Skipping ROI for embedding, failed to read: {exc}")
        return items

    @classmethod
    def compute_embeddings_payload(
        cls,
        items: list[tuple[UUID, np.ndarray, tuple]],
        embedding_model: Embedding,
        generation: int,
        progress_callback: Callable[[int, int], None] | None = None,
        batch_callback: Callable[[tuple], None] | None = None,
    ) -> tuple[int, str | None, list[tuple[UUID, object, tuple]]]:
        """Embed *items* (from :meth:`snapshot`) in chunks.

        Each finished chunk goes to *batch_callback* (when given) instead of
        into the returned payload, so results arrive as they're made. Every
        payload names the model, so results of a model replaced meanwhile
        can be told apart. A failed chunk is logged and skipped; only "model
        not available" stops the run.
        """
        model_name = getattr(embedding_model, "model_name", None)
        if not items:
            return generation, model_name, []
        total = len(items)
        if progress_callback is not None:
            progress_callback(0, total)
        kept: list[tuple[UUID, object, tuple]] = []
        failed = 0
        for start in range(0, total, cls.CHUNK):
            chunk = items[start : start + cls.CHUNK]
            try:
                vectors = embedding_model.embed_many([image for _u, image, _b in chunk])
            except Exception as exc:
                if "not available" in str(exc).lower():
                    raise
                failed += len(chunk)
                LOGGER.warning(f"Embedding {len(chunk)} tiles failed: {exc}")
                vectors = []
            rows = (
                [
                    (uuid, vector, box)
                    for (uuid, _image, box), vector in zip(chunk, vectors, strict=True)
                ]
                if vectors
                else []
            )
            if rows:
                if batch_callback is not None:
                    batch_callback((generation, model_name, rows))
                else:
                    kept.extend(rows)
            if progress_callback is not None:
                progress_callback(min(start + cls.CHUNK, total), total)
        if failed:
            LOGGER.warning(
                f"{failed:,} of {total:,} tile embeddings could not be computed"
            )
        return generation, model_name, kept

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
