from __future__ import annotations

from PyQt6 import QtCore
from typing import Any, cast

from vars_gridview.controllers.selection_model import SelectionModel
from vars_gridview.ui.coordinators.mosaic_selection_coordinator import (
    MosaicSelectionCoordinator,
)


class _FakeWidget:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_selected = False
        self.update_calls = 0
        self.visible = True

    def update(self) -> None:
        self.update_calls += 1

    def isVisible(self) -> bool:
        return self.visible


class _FakeMosaicView:
    def __init__(self) -> None:
        self.ensure_visible_calls: list[object] = []

    def visible_widgets_in_range(
        self,
        *,
        all_widgets: list,
        begin_index: int,
        end_index: int,
    ) -> list:
        selected = []
        for idx in range(begin_index, end_index + 1):
            widget = all_widgets[idx]
            if widget.isVisible():
                selected.append(widget)
        return selected

    def ensure_widget_visible_if_needed(self, widget: object) -> None:
        self.ensure_visible_calls.append(widget)


def test_select_and_deselect() -> None:
    model = SelectionModel()
    view = _FakeMosaicView()
    widgets = [_FakeWidget("a"), _FakeWidget("b")]
    coordinator = MosaicSelectionCoordinator(
        parent=model,
        selection_model=model,
        mosaic_view=cast(Any, view),
        all_widgets_getter=lambda: widgets,
    )

    coordinator.select(widgets[0], clear=True)
    assert model.selected == [widgets[0]]

    coordinator.select(widgets[1], clear=False)
    assert model.selected == [widgets[0], widgets[1]]

    coordinator.deselect(widgets[0])
    assert model.selected == [widgets[1]]


def test_select_range_uses_visible_only() -> None:
    model = SelectionModel()
    view = _FakeMosaicView()
    widgets = [_FakeWidget("a"), _FakeWidget("b"), _FakeWidget("c")]
    widgets[1].visible = False
    coordinator = MosaicSelectionCoordinator(
        parent=model,
        selection_model=model,
        mosaic_view=cast(Any, view),
        all_widgets_getter=lambda: widgets,
    )

    coordinator.select_range(widgets[0], widgets[2])
    assert model.selected == [widgets[0], widgets[2]]


def test_update_widget_selection_flags() -> None:
    model = SelectionModel()
    view = _FakeMosaicView()
    widgets = [_FakeWidget("a"), _FakeWidget("b")]
    coordinator = MosaicSelectionCoordinator(
        parent=model,
        selection_model=model,
        mosaic_view=cast(Any, view),
        all_widgets_getter=lambda: widgets,
    )

    coordinator.update_widget_selection_flags([widgets[1]])
    assert widgets[0].is_selected is False
    assert widgets[1].is_selected is True
    assert widgets[0].update_calls == 0
    assert widgets[1].update_calls == 1


def test_select_relative_moves_and_scrolls() -> None:
    model = SelectionModel()
    view = _FakeMosaicView()
    widgets = [_FakeWidget("a"), _FakeWidget("b"), _FakeWidget("c")]
    coordinator = MosaicSelectionCoordinator(
        parent=model,
        selection_model=model,
        mosaic_view=cast(Any, view),
        all_widgets_getter=lambda: widgets,
    )

    model.set_selection(cast(list, [widgets[1]]))
    activated: list[object] = []

    handled = coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=2,
        activate_callback=lambda widget: activated.append(widget),
    )

    assert handled is True
    assert model.selected == []
    assert activated == [widgets[2]]
    assert view.ensure_visible_calls == [widgets[2]]
