from __future__ import annotations

from typing import Any, cast

from PyQt6 import QtCore

from vars_gridview.ui.coordinators.mosaic_tile_action_coordinator import (
    MosaicTileActionCoordinator,
)


class _Rect:
    pass


def test_handle_label_action_uses_picker_and_callback() -> None:
    parent = QtCore.QObject()
    rect = _Rect()
    called: list[tuple[object, str, str]] = []

    coordinator = MosaicTileActionCoordinator(
        parent=parent,
        dialog_parent=None,
        concept_provider=lambda: ["fish"],
        part_provider=lambda: ["head"],
        label_action_callback=lambda rw, c, p: called.append((rw, c, p)),
        verify_action_callback=None,
        mark_training_action_callback=None,
        concept_picker=lambda _parent, _concepts, _parts: ("fish", "head"),
    )

    coordinator.handle_label_action(cast(Any, rect))

    assert called == [(rect, "fish", "head")]


def test_handle_label_action_cancel_no_callback() -> None:
    parent = QtCore.QObject()
    rect = _Rect()
    called = {"value": 0}

    coordinator = MosaicTileActionCoordinator(
        parent=parent,
        dialog_parent=None,
        concept_provider=lambda: ["fish"],
        part_provider=lambda: ["head"],
        label_action_callback=lambda _rw, _c, _p: called.__setitem__(
            "value", called["value"] + 1
        ),
        verify_action_callback=None,
        mark_training_action_callback=None,
        concept_picker=lambda _parent, _concepts, _parts: None,
    )

    coordinator.handle_label_action(cast(Any, rect))

    assert called["value"] == 0


def test_verify_and_mark_training_callbacks() -> None:
    parent = QtCore.QObject()
    rect = _Rect()
    verify_called = {"value": 0}
    train_called = {"value": 0}

    coordinator = MosaicTileActionCoordinator(
        parent=parent,
        dialog_parent=None,
        concept_provider=None,
        part_provider=None,
        label_action_callback=None,
        verify_action_callback=lambda _rw: verify_called.__setitem__(
            "value", verify_called["value"] + 1
        ),
        mark_training_action_callback=lambda _rw: train_called.__setitem__(
            "value", train_called["value"] + 1
        ),
        concept_picker=None,
    )

    coordinator.handle_verify_action(cast(Any, rect))
    coordinator.handle_mark_training_action(cast(Any, rect))

    assert verify_called["value"] == 1
    assert train_called["value"] == 1
