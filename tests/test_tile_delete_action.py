"""Right-click Delete on a tile: the whole selection when the tile is part of
it, otherwise only that tile; nothing without confirmation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6 import QtWidgets

from vars_gridview.ui.coordinators.annotation_action_coordinator import (
    AnnotationActionCoordinator,
)


class _FakeMosaic:
    def __init__(self, selected: list) -> None:
        self.selected = list(selected)

    def get_selected(self) -> list:
        return list(self.selected)

    def select(self, rect, clear: bool = True) -> None:
        self.selected = [rect]


def _coordinator(mosaic, monkeypatch, answer):
    coordinator = AnnotationActionCoordinator(
        parent=None,
        image_mosaic=mosaic,
        annotation_controller_getter=lambda: object(),
        kb_service_getter=lambda: None,
        settings=SimpleNamespace(username=SimpleNamespace(value="tester")),
    )
    asked: list[str] = []

    def question(_parent, _title, text, *args, **kwargs):
        asked.append(text)
        return answer

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", question)
    dispatched: list[list] = []
    monkeypatch.setattr(coordinator, "_dispatch_delete", dispatched.append)
    return coordinator, asked, dispatched


@pytest.mark.parametrize(
    ("selected", "clicked", "expected", "count_text"),
    [
        (["a", "b", "c"], "b", ["a", "b", "c"], "3 localizations"),
        (["a", "b"], "z", ["z"], "this localization"),
        ([], "z", ["z"], "this localization"),
    ],
)
def test_delete_from_tile_targets(monkeypatch, selected, clicked, expected, count_text):
    mosaic = _FakeMosaic(selected)
    coordinator, asked, dispatched = _coordinator(
        mosaic, monkeypatch, QtWidgets.QMessageBox.StandardButton.Yes
    )

    coordinator.delete_from_tile(clicked)

    assert dispatched == [expected]
    assert count_text in asked[0]


def test_delete_from_tile_does_nothing_when_not_confirmed(monkeypatch):
    coordinator, _asked, dispatched = _coordinator(
        _FakeMosaic(["a"]), monkeypatch, QtWidgets.QMessageBox.StandardButton.No
    )

    coordinator.delete_from_tile("a")

    assert dispatched == []
