"""Coordinator for similarity sorting ("Find similar") in the mosaic.

Ranks tiles by cosine similarity to the clicked tile using the embeddings
the tiles already hold -- from the VARS vector database, or computed in the
background -- in one matrix product (milliseconds for thousands of tiles).

It used to compute each distance through ``RectWidget.embedding``, which
embedded any tile without a cached vector one HTTP call at a time on a worker
behind a modal progress dialog with no cancel: on a fresh page that could
lock the window for minutes. Now tiles without an embedding yet are simply
placed last (and the status line says how many), and only the clicked tile is
embedded on demand if it has none.

The ranking is applied as an order of tiles, not of indices, onto whatever
the grid holds by then, so a delete finishing in between can't misapply it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


def rank_by_similarity(
    query: np.ndarray,
    embeddings: list[np.ndarray | None],
    labels: list[str],
    query_label: str,
    same_class_only: bool,
) -> tuple[list[int], int]:
    """Indices of *embeddings* from most to least similar to *query*.

    Tiles with another label (when *same_class_only*) come after all
    matching ones, and tiles without an embedding come last; both keep their
    current relative order. Returns ``(order, missing)`` where *missing* counts
    the tiles that had no embedding.
    """
    q = np.asarray(query, dtype=np.float32).ravel()
    q = q / (np.linalg.norm(q) or 1.0)
    have = [i for i, e in enumerate(embeddings) if e is not None]
    missing = len(embeddings) - len(have)
    similarity = np.full(len(embeddings), -np.inf, dtype=np.float32)
    if have:
        matrix = np.stack([np.asarray(embeddings[i], np.float32).ravel() for i in have])
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1.0
        similarity[have] = (matrix @ q) / norms
    groups = []
    for i in range(len(embeddings)):
        if embeddings[i] is None:
            group = 2
        elif same_class_only and labels[i] != query_label:
            group = 1
        else:
            group = 0
        groups.append(group)
    # Stable: equal keys keep the current order.
    order = sorted(
        range(len(embeddings)),
        key=lambda i: (groups[i], -float(similarity[i]) if groups[i] == 0 else 0.0),
    )
    return order, missing


class MosaicSimilarityCoordinator(QtCore.QObject):
    """Rank the mosaic by similarity to a clicked tile."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget | None,
        rect_widgets_getter: Callable[[], list[RectWidget]],
        apply_order: Callable[[list[RectWidget]], None],
        sort_unavailable_callback: Callable[[str], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._rect_widgets_getter = rect_widgets_getter
        self._apply_order = apply_order
        self._sort_unavailable_callback = sort_unavailable_callback
        self._status_callback = status_callback
        self._request = 0

    def start(self, clicked_rect: RectWidget, same_class_only: bool) -> None:
        """Sort by similarity to *clicked_rect*; embeds it first if needed."""
        self._request += 1
        request = self._request
        if clicked_rect.has_cached_embedding:
            self._sort(clicked_rect, same_class_only)
            return
        model = getattr(clicked_rect, "_embedding_model", None)
        if model is None or not clicked_rect.roi_loaded or clicked_rect.roi is None:
            self._unavailable(
                "This tile has no embedding: it isn't in the VARS vector "
                "database and the embedding service isn't available (or the "
                "image hasn't loaded yet)."
            )
            return
        box = clicked_rect.association.box
        roi = clicked_rect.roi[:, :, ::-1].copy()  # plain data for the worker
        worker = Worker(model.embed, roi)
        worker.signals.result.connect(
            lambda embedding: self._on_clicked_embedded(
                request, clicked_rect, tuple(box), embedding, same_class_only
            )
        )
        worker.signals.error.connect(
            lambda err: self._unavailable(f"Could not embed the tile: {err[1]}")
        )
        QtCore.QThreadPool.globalInstance().start(worker)

    def _on_clicked_embedded(
        self, request, clicked_rect, box, embedding, same_class_only
    ) -> None:
        if request != self._request:
            return  # a newer Find similar replaced this one
        if clicked_rect not in self._rect_widgets_getter():
            return  # tile gone (new page, deleted)
        if tuple(clicked_rect.association.box) == box:
            clicked_rect.cache_embedding(embedding)
        self._sort(clicked_rect, same_class_only, query=embedding)

    def _sort(
        self,
        clicked_rect: RectWidget,
        same_class_only: bool,
        query: np.ndarray | None = None,
    ) -> None:
        rect_widgets = list(self._rect_widgets_getter())
        if not rect_widgets:
            return
        embeddings = [
            rw._embedding if rw.has_cached_embedding else None for rw in rect_widgets
        ]
        query = clicked_rect._embedding if query is None else query
        order, missing = rank_by_similarity(
            query,
            embeddings,
            [rw.text_label for rw in rect_widgets],
            clicked_rect.text_label,
            same_class_only,
        )
        self._apply_order([rect_widgets[i] for i in order])
        if self._status_callback is not None:
            ranked = len(rect_widgets) - missing
            self._status_callback(
                f"Sorted by similarity: {ranked:,} of {len(rect_widgets):,} tiles "
                f"ranked; {missing:,} without an embedding yet are after them"
                if missing
                else f"Sorted by similarity: all {ranked:,} tiles ranked"
            )

    def _unavailable(self, message: str) -> None:
        LOGGER.warning(f"Find similar: {message}")
        if self._sort_unavailable_callback is not None:
            self._sort_unavailable_callback(message)


__all__ = ["MosaicSimilarityCoordinator", "rank_by_similarity"]
