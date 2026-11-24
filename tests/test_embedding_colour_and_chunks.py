from __future__ import annotations

from uuid import uuid4

import cv2
import numpy as np
import pytest

from vars_gridview.lib.vision.embedding import HttpEmbedding
from vars_gridview.ui.coordinators.mosaic_embedding_coordinator import (
    MosaicEmbeddingCoordinator,
)


def test_png_sent_to_the_service_keeps_rgb_colours() -> None:
    rgb = np.zeros((4, 4, 3), np.uint8)
    rgb[..., 0] = 255  # pure red, in RGB order (the Embedding contract)

    png = HttpEmbedding._encode_png_bytes(rgb)

    # Any standard PNG reader (the service's) must see red. OpenCV decodes
    # to BGR, so red is its last channel.
    bgr = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    assert bgr[0, 0].tolist() == [0, 0, 255]


class _Tile:
    def __init__(self, value: int) -> None:
        self.association_uuid = uuid4()
        self.roi_loaded = True
        self.roi = np.full((2, 2, 3), value, np.uint8)
        self.roi_box = (value, 0, value + 1, 1)


class _Model:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    def embed_many(self, images, progress_callback=None):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("timeout")
        return [np.array([float(img[0, 0, 0])], np.float32) for img in images]


def test_precompute_delivers_chunks_as_they_finish(monkeypatch) -> None:
    monkeypatch.setattr(MosaicEmbeddingCoordinator, "CHUNK", 3)
    tiles = [_Tile(i) for i in range(7)]
    batches: list[list] = []

    generation, _model, rest = MosaicEmbeddingCoordinator.compute_embeddings_payload(
        MosaicEmbeddingCoordinator.snapshot(tiles),
        _Model(),
        5,
        None,
        lambda payload: batches.append(payload),
    )

    assert (generation, rest) == (5, [])
    assert [len(rows) for _gen, _m, rows in batches] == [3, 3, 1]
    delivered = {u: float(v[0]) for _gen, _m, rows in batches for u, v, _b in rows}
    assert delivered == {t.association_uuid: float(i) for i, t in enumerate(tiles)}


def test_precompute_keeps_other_chunks_when_one_fails(monkeypatch) -> None:
    monkeypatch.setattr(MosaicEmbeddingCoordinator, "CHUNK", 2)
    tiles = [_Tile(i) for i in range(6)]
    batches: list = []

    MosaicEmbeddingCoordinator.compute_embeddings_payload(
        MosaicEmbeddingCoordinator.snapshot(tiles),
        _Model(fail_on_call=2),
        1,
        None,
        batches.append,
    )

    got = {u for _gen, _m, rows in batches for u, _v, _b in rows}
    assert got == {tiles[i].association_uuid for i in (0, 1, 4, 5)}


def test_precompute_stops_when_the_model_is_not_available() -> None:
    class _Gone:
        def embed_many(self, images, progress_callback=None):
            raise RuntimeError("Embedding model 'x' is not available.")

    with pytest.raises(RuntimeError, match="not available"):
        MosaicEmbeddingCoordinator.compute_embeddings_payload(
            MosaicEmbeddingCoordinator.snapshot([_Tile(1)]),
            _Gone(),
            1,
            None,
            lambda _p: None,
        )
