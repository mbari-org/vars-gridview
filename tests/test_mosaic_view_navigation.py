from PyQt6 import QtCore

from vars_gridview.ui.mosaic.mosaic_view import MosaicView


def test_compute_relative_index_left_right() -> None:
    assert (
        MosaicView.compute_relative_index(
            current_index=2,
            key=QtCore.Qt.Key.Key_Left,
            columns=3,
            total_items=10,
        )
        == 1
    )
    assert (
        MosaicView.compute_relative_index(
            current_index=2,
            key=QtCore.Qt.Key.Key_Right,
            columns=3,
            total_items=10,
        )
        == 3
    )


def test_compute_relative_index_up_down() -> None:
    assert (
        MosaicView.compute_relative_index(
            current_index=5,
            key=QtCore.Qt.Key.Key_Up,
            columns=3,
            total_items=10,
        )
        == 2
    )
    assert (
        MosaicView.compute_relative_index(
            current_index=5,
            key=QtCore.Qt.Key.Key_Down,
            columns=3,
            total_items=10,
        )
        == 8
    )


def test_compute_relative_index_out_of_bounds_returns_none() -> None:
    assert (
        MosaicView.compute_relative_index(
            current_index=0,
            key=QtCore.Qt.Key.Key_Left,
            columns=3,
            total_items=10,
        )
        is None
    )
    assert (
        MosaicView.compute_relative_index(
            current_index=9,
            key=QtCore.Qt.Key.Key_Right,
            columns=3,
            total_items=10,
        )
        is None
    )


def test_compute_relative_index_invalid_inputs_return_none() -> None:
    assert (
        MosaicView.compute_relative_index(
            current_index=-1,
            key=QtCore.Qt.Key.Key_Right,
            columns=3,
            total_items=10,
        )
        is None
    )
    assert (
        MosaicView.compute_relative_index(
            current_index=1,
            key=QtCore.Qt.Key.Key_Right,
            columns=0,
            total_items=10,
        )
        is None
    )
    assert (
        MosaicView.compute_relative_index(
            current_index=1,
            key=QtCore.Qt.Key.Key_Space,
            columns=3,
            total_items=10,
        )
        is None
    )
