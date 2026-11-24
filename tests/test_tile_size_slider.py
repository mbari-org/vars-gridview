"""The tile size slider above the grid."""

from __future__ import annotations

import pytest
from PyQt6 import QtWidgets

from vars_gridview.ui.style import UiGeometry
from vars_gridview.ui.widgets.mosaic_controls_bar import MosaicControlsBar


@pytest.fixture
def bar() -> MosaicControlsBar:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return MosaicControlsBar()


def test_range_matches_zoom_box(bar: MosaicControlsBar) -> None:
    slider = bar.tile_size_slider
    assert (slider.minimum(), slider.maximum()) == (
        UiGeometry.ZOOM_MIN,
        UiGeometry.ZOOM_MAX,
    )
    assert bar.tile_size == UiGeometry.ZOOM_DEFAULT


def test_drag_updates_label_now_and_emits_once(bar: MosaicControlsBar) -> None:
    emitted: list[int] = []
    bar.tileSizeChanged.connect(emitted.append)

    for value in (70, 90, 120):
        bar.tile_size_slider.setValue(value)

    assert bar.tile_size_value.text() == "120%"
    assert emitted == []  # debounced: the grid isn't re-laid out mid-drag
    bar._tile_size_timer.timeout.emit()
    assert emitted == [120]


def test_set_tile_size_follows_without_emitting(bar: MosaicControlsBar) -> None:
    emitted: list[int] = []
    bar.tileSizeChanged.connect(emitted.append)

    bar.set_tile_size(150)

    assert bar.tile_size == 150
    assert bar.tile_size_value.text() == "150%"
    assert not bar._tile_size_timer.isActive()
    assert emitted == []


def test_reset_view_keeps_tile_size(bar: MosaicControlsBar) -> None:
    bar.set_tile_size(150)
    bar.brightness_slider.setValue(40)

    bar.reset_view()

    assert bar.brightness_slider.value() == 0
    assert bar.tile_size == 150
