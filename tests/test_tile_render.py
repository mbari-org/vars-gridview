"""Tile pictures: the cached source step, and building adjusted pictures off
the GUI thread."""

from __future__ import annotations

import uuid

import numpy as np
from PyQt6 import QtWidgets

import vars_gridview.lib.annotation  # noqa: F401  (import order)
from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.annotation.observation import Observation
from vars_gridview.lib.vision.display_adjust import ColourCorrector, DisplayAdjustment
from vars_gridview.ui.mosaic import rect_widget as rw
from vars_gridview.ui.mosaic.rect_widget import (
    DisplayContext,
    RectWidget,
    SourceEntry,
    render_tile,
)

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FRINGES = DisplayAdjustment(fix_fringes=True, colour_correct=True)


def _roi(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (90, 120, 3), dtype=np.uint8)


def _tile() -> RectWidget:
    obs = Observation(
        uuid=uuid.uuid4(),
        concept="Pyrosoma",
        observer="t",
        group="",
        imaged_moment_uuid=uuid.uuid4(),
    )
    association = BoundingBoxAssociation(
        uuid.uuid4(), {"x": 0, "y": 0, "width": 10, "height": 10}, obs, "self"
    )
    tile = RectWidget(
        [association],
        "http://x",
        True,
        {},
        {},
        0,
        *(lambda *a: None,) * 5,
        text_label="Pyrosoma",
        preload_roi=False,
    )
    tile.roi = _roi()
    tile._roi_loaded = True
    tile.set_display_context(DisplayContext())
    return tile


def _finish_renders() -> None:
    rw._tile_render_pool().waitForDone()
    QtWidgets.QApplication.processEvents()


def test_render_tile_returns_a_tile_sized_image_and_a_source() -> None:
    image, source = render_tile(_roi(), FRINGES, ColourCorrector(), None, 240, 240)
    assert (image.width(), image.height()) == (240, 240)
    assert source is not None


def test_neutral_render_has_no_source_to_cache() -> None:
    _image, source = render_tile(_roi(), DisplayAdjustment(), None, None, 240, 240)
    assert source is None


def test_cached_source_skips_the_source_step(monkeypatch) -> None:
    roi = _roi()
    _image, source = render_tile(roi, FRINGES, ColourCorrector(), None, 240, 240)

    def boom(*_args, **_kwargs):
        raise AssertionError("source step ran again")

    monkeypatch.setattr(rw, "adjust_source", boom)
    brighter = DisplayAdjustment(fix_fringes=True, colour_correct=True, brightness=30)
    image, new_source = render_tile(
        roi, brighter, ColourCorrector(), None, 240, 240, source
    )
    assert image.width() == 240
    assert new_source is None


def test_cached_source_needs_same_crop_and_key() -> None:
    context = DisplayContext()
    roi = _roi()
    entry = SourceEntry(roi, ("k",), roi, 1.0)
    context.store_source(1, entry)

    assert context.cached_source(1, roi, ("k",)) is entry
    assert context.cached_source(1, roi.copy(), ("k",)) is None  # new crop
    assert context.cached_source(1, roi, ("other",)) is None  # new settings
    context.forget_source(1)
    assert context.cached_source(1, roi, ("k",)) is None


def test_source_cache_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr(rw, "MAX_CACHED_SOURCES", 3)
    context = DisplayContext()
    roi = _roi()
    for tile_id in range(5):
        context.store_source(tile_id, SourceEntry(roi, (), roi, 1.0))
    assert [context.cached_source(i, roi, ()) is not None for i in range(5)] == [
        False,
        False,
        True,
        True,
        True,
    ]


def test_source_key_tracks_only_source_settings() -> None:
    context = DisplayContext()
    context.set_adjustment(FRINGES)
    key = context.source_key(("f", 1))
    context.set_adjustment(
        DisplayAdjustment(fix_fringes=True, colour_correct=True, brightness=40)
    )
    assert context.source_key(("f", 1)) == key
    context.set_adjustment(DisplayAdjustment(fix_fringes=True))
    assert context.source_key(("f", 1)) != key


def test_neutral_tile_renders_immediately() -> None:
    tile = _tile()
    tile._refresh_pic()
    assert not tile._pic_dirty
    assert tile._render_token is None


def test_adjusted_tile_renders_on_a_worker() -> None:
    tile = _tile()
    tile._display.set_adjustment(FRINGES)
    old_pic = tile.pic

    tile._refresh_pic()
    assert tile.pic is old_pic  # old picture shown until the new one is ready
    assert tile._render_token is not None
    tile._refresh_pic()  # a repaint meanwhile doesn't start a second build

    _finish_renders()
    assert tile.pic is not old_pic
    assert not tile._pic_dirty
    assert tile._pic_version == tile._display.version
    assert tile._render_token is None
    # The source step was cached: a brightness change reuses it.
    key = tile._display.source_key(tile.frame_key)
    assert tile._display.cached_source(tile._tile_id, tile.roi, key) is not None


def test_superseded_render_is_dropped() -> None:
    tile = _tile()
    tile._display.set_adjustment(FRINGES)
    old_pic = tile.pic
    tile._refresh_pic()
    tile.roi = _roi(1)  # a new crop arrives before the build finishes
    tile._mark_pic_dirty()

    _finish_renders()
    assert tile.pic is old_pic
    assert tile._pic_dirty


def test_render_result_for_deleted_tile_is_ignored() -> None:
    tile = _tile()
    tile._display.set_adjustment(FRINGES)
    old_pic = tile.pic
    tile._refresh_pic()
    tile._deleted = True
    _finish_renders()
    assert tile.pic is old_pic
