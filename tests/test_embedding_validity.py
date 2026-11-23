"""An embedding only counts for the box and the model it was made with."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import numpy as np
from PyQt6 import QtWidgets

import vars_gridview.lib.annotation  # noqa: F401  (import order)
from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.annotation.observation import Observation
from vars_gridview.ui.coordinators.embedding_lifecycle_coordinator import (
    EmbeddingLifecycleCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    MosaicSimilarityCoordinator,
)
from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
from vars_gridview.ui.mosaic.rect_widget import RectWidget

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _assoc(x: int) -> BoundingBoxAssociation:
    obs = Observation(
        uuid=uuid.uuid4(),
        concept="Pyrosoma",
        observer="t",
        group="",
        imaged_moment_uuid=uuid.uuid4(),
    )
    return BoundingBoxAssociation(
        uuid.uuid4(), {"x": x, "y": 0, "width": 10, "height": 10}, obs, "self"
    )


def _tile(associations, index=0) -> RectWidget:
    return RectWidget(
        associations,
        "http://x",
        True,
        {},
        {},
        index,
        *(lambda *a: None,) * 5,
        text_label="Pyrosoma",
        preload_roi=False,
    )


def _move(association: BoundingBoxAssociation, x: int) -> None:
    association.update_data(x=x, y=0, width=10, height=10)


def _fake_mosaic(tiles, space="dinov3"):
    return SimpleNamespace(
        _embedding_generation=1, _embedding_space=space, _rect_widgets=list(tiles)
    )


def test_vector_of_an_edited_box_is_not_used() -> None:
    a = _assoc(0)
    tile = _tile([a])
    old_box = tuple(a.box)
    _move(a, 50)  # edited while its old image was being embedded

    rows = [(a.uuid, np.ones(4, np.float32), old_box)]
    ImageMosaic._on_embeddings_precomputed(_fake_mosaic([tile]), (1, "dinov3", rows))

    assert not tile.has_cached_embedding  # recomputed, not kept forever


def test_vector_of_the_current_box_is_used() -> None:
    a = _assoc(0)
    tile = _tile([a])
    rows = [(a.uuid, np.ones(4, np.float32), tuple(a.box))]

    ImageMosaic._on_embeddings_precomputed(_fake_mosaic([tile]), (1, "dinov3", rows))

    assert tile.has_cached_embedding and tile.embedding_space == "dinov3"


def test_vectors_of_a_replaced_model_are_dropped() -> None:
    a = _assoc(0)
    tile = _tile([a])
    rows = [(a.uuid, np.ones(4, np.float32), tuple(a.box))]

    ImageMosaic._on_embeddings_precomputed(
        _fake_mosaic([tile], space="bioclip2-image"), (1, "dinov3", rows)
    )

    assert not tile.has_cached_embedding


def test_box_edited_through_another_tile_of_the_frame_invalidates() -> None:
    # Two boxes in one frame: each tile holds both associations.
    a0, a1 = _assoc(0), _assoc(30)
    tile_a = _tile([a0, a1], 0)
    tile_b = _tile([a0, a1], 1)
    tile_b.cache_embedding(np.ones(4, np.float32), space="dinov3")

    _move(a1, 100)  # dragged in the image view opened from tile A

    assert not tile_b.has_cached_embedding
    refreshed = []
    tile_b.request_roi_refresh = lambda **k: refreshed.append(tile_b)
    tile_a.request_roi_refresh = lambda **k: refreshed.append(tile_a)
    assert ImageMosaic.refresh_tiles_for_association(_fake_mosaic([tile_a, tile_b]), a1)
    assert refreshed == [tile_b]  # the tile showing that box, not the clicked one


def test_ranking_ignores_other_models_and_other_lengths() -> None:
    tiles = [_tile([_assoc(i)]) for i in range(3)]
    tiles[0].cache_embedding(np.array([1.0, 0.0], np.float32), space="dinov3")
    tiles[1].cache_embedding(np.array([1.0, 0.1], np.float32), space="dinov3")
    tiles[2].cache_embedding(np.ones(5, np.float32), space="siglip2-image")
    applied, status = [], []
    coordinator = MosaicSimilarityCoordinator(
        parent=None,
        dialog_parent=None,
        rect_widgets_getter=lambda: tiles,
        apply_order=applied.append,
        status_callback=status.append,
        space_getter=lambda: "dinov3",
    )

    coordinator.start(tiles[0], False)  # used to raise on the 5-long vector

    assert applied == [[tiles[0], tiles[1], tiles[2]]]
    assert "2 of 3 tiles ranked" in status[0]


def test_model_built_from_old_settings_is_not_labelled_with_new_ones() -> None:
    settings = SimpleNamespace(
        embedding_service_url=SimpleNamespace(value="http://svc:5000/"),
        embedding_model_name=SimpleNamespace(value="siglip2-image"),
    )
    applied = []
    fake = SimpleNamespace(
        _settings=settings,
        _embedding_model=None,
        _loaded_embedding_config=None,
        _pending_embedding_reload=False,
        _apply_model_callback=applied.append,
    )
    fake._current_embedding_config = lambda: (
        EmbeddingLifecycleCoordinator._current_embedding_config(fake)
    )
    old = SimpleNamespace(base_url="http://svc:5000", model_name="bioclip2-image")

    EmbeddingLifecycleCoordinator._on_embedding_model_ready(fake, old)

    assert applied == [] and fake._pending_embedding_reload  # reload the new one
