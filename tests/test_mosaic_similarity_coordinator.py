from __future__ import annotations

import numpy as np

from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    rank_by_similarity,
)


def _v(*xs: float) -> np.ndarray:
    return np.asarray(xs, dtype=np.float32)


def test_rank_by_similarity_basic() -> None:
    query = _v(1, 0)
    embeddings = [_v(0, 1), _v(1, 0.1), _v(1, 1)]  # cos ~0, ~0.995, ~0.707

    order, missing = rank_by_similarity(
        query, embeddings, ["fish"] * 3, "fish", same_class_only=False
    )

    assert order == [1, 2, 0]
    assert missing == 0


def test_rank_by_similarity_same_class_only_puts_other_labels_after() -> None:
    query = _v(1, 0)
    embeddings = [_v(1, 0), _v(0.5, 0.5), _v(0, 1)]

    order, _missing = rank_by_similarity(
        query, embeddings, ["coral", "fish", "fish"], "fish", same_class_only=True
    )

    assert order == [1, 2, 0]  # the identical coral comes after every fish


def test_rank_by_similarity_tiles_without_embeddings_go_last_in_order() -> None:
    query = _v(1, 0)
    embeddings = [None, _v(0, 1), None, _v(1, 0)]

    order, missing = rank_by_similarity(
        query, embeddings, ["fish"] * 4, "fish", same_class_only=False
    )

    assert order == [3, 1, 0, 2]
    assert missing == 2
