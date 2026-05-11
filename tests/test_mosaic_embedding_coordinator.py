from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import numpy as np

from vars_gridview.ui.coordinators.mosaic_embedding_coordinator import (
    MosaicEmbeddingCoordinator,
)


class _Rect:
    def __init__(self, *, roi_loaded: bool, roi, association_uuid) -> None:
        self.roi_loaded = roi_loaded
        self.roi = roi
        self.association_uuid = association_uuid


class _EmbeddingModel:
    def embed_many(self, roi_images, progress_callback=None):
        if progress_callback is not None:
            progress_callback(len(roi_images), len(roi_images))
        return [float(img.sum()) for img in roi_images]


def test_compute_embeddings_payload_filters_unloaded_and_none_roi() -> None:
    good_uuid = uuid4()
    rects = [
        _Rect(
            roi_loaded=False,
            roi=np.zeros((2, 2, 3), dtype=np.uint8),
            association_uuid=uuid4(),
        ),
        _Rect(roi_loaded=True, roi=None, association_uuid=uuid4()),
        _Rect(
            roi_loaded=True,
            roi=np.ones((2, 2, 3), dtype=np.uint8),
            association_uuid=good_uuid,
        ),
    ]

    generation, rows = MosaicEmbeddingCoordinator.compute_embeddings_payload(
        rect_widgets=cast(Any, rects),
        embedding_model=cast(Any, _EmbeddingModel()),
        generation=7,
        progress_callback=None,
    )

    assert generation == 7
    assert len(rows) == 1
    assert rows[0][0] == good_uuid


def test_compute_embeddings_payload_returns_empty_when_no_candidates() -> None:
    rects = [_Rect(roi_loaded=False, roi=None, association_uuid=uuid4())]

    generation, rows = MosaicEmbeddingCoordinator.compute_embeddings_payload(
        rect_widgets=cast(Any, rects),
        embedding_model=cast(Any, _EmbeddingModel()),
        generation=3,
        progress_callback=None,
    )

    assert generation == 3
    assert rows == []
