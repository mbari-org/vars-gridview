"""Right-click Label / Verify / Mark Training / Verify + Mark Training on a
tile: the whole selection when the tile is part of it, otherwise only that
tile. More than one localization asks first."""

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


class _FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def label_selected(self, associations, concept, part, observer):
        self.calls.append(("label", associations, concept, part))

    def verify_selected(self, associations, state, observer):
        self.calls.append(("verify", associations, state))

    def mark_training_selected(self, associations, state, observer):
        self.calls.append(("mark_training", associations, state))

    def verify_and_mark_training_selected(self, associations, observer):
        self.calls.append(("verify_and_mark", associations))


def _tile(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, association=f"assoc-{name}")


def _setup(monkeypatch, selected, answer=QtWidgets.QMessageBox.StandardButton.Yes):
    mosaic = _FakeMosaic(selected)
    controller = _FakeController()
    coordinator = AnnotationActionCoordinator(
        parent=None,
        image_mosaic=mosaic,
        annotation_controller_getter=lambda: controller,
        kb_service_getter=lambda: None,
        settings=SimpleNamespace(username=SimpleNamespace(value="tester")),
    )
    asked: list[str] = []

    def question(_parent, _title, text, *args, **kwargs):
        asked.append(text)
        return answer

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", question)
    return coordinator, mosaic, controller, asked


ACTIONS = [
    (lambda c, t: c.verify_single_from_tile(t), "verify"),
    (lambda c, t: c.mark_training_single_from_tile(t), "mark_training"),
    (lambda c, t: c.verify_and_mark_training_from_tile(t), "verify_and_mark"),
    (lambda c, t: c.label_single_from_tile(t, "Pyrosoma", "self"), "label"),
]


@pytest.mark.parametrize(("run", "kind"), ACTIONS)
def test_tile_in_selection_acts_on_whole_selection(monkeypatch, run, kind):
    a, b, c = _tile("a"), _tile("b"), _tile("c")
    coordinator, mosaic, controller, asked = _setup(monkeypatch, [a, b, c])

    run(coordinator, b)

    assert [call[0] for call in controller.calls] == [kind]
    assert controller.calls[0][1] == ["assoc-a", "assoc-b", "assoc-c"]
    assert "3 localizations" in asked[0]
    assert mosaic.selected == [a, b, c]  # selection kept


@pytest.mark.parametrize(("run", "kind"), ACTIONS)
def test_tile_outside_selection_acts_on_that_tile_only(monkeypatch, run, kind):
    a, b, z = _tile("a"), _tile("b"), _tile("z")
    coordinator, mosaic, controller, asked = _setup(monkeypatch, [a, b])

    run(coordinator, z)

    assert controller.calls[0][:2] == (kind, ["assoc-z"])
    assert asked == []  # one localization: no confirmation, as before
    assert mosaic.selected == [z]


def test_declined_confirmation_changes_nothing(monkeypatch):
    a, b = _tile("a"), _tile("b")
    coordinator, _mosaic, controller, _asked = _setup(
        monkeypatch, [a, b], QtWidgets.QMessageBox.StandardButton.No
    )

    coordinator.verify_single_from_tile(a)

    assert controller.calls == []
    assert coordinator.pending_action is None


def test_verify_and_mark_is_a_single_operation(monkeypatch):
    a, b = _tile("a"), _tile("b")
    coordinator, _mosaic, controller, _asked = _setup(monkeypatch, [a, b])

    coordinator.verify_and_mark_training_from_tile(a)

    assert len(controller.calls) == 1  # not verify, then a refused mark
