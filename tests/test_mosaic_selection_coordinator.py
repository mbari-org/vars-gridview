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


def _make_coordinator(
    widgets: list,
) -> tuple[SelectionModel, _FakeMosaicView, MosaicSelectionCoordinator]:
    model = SelectionModel()
    view = _FakeMosaicView()
    coordinator = MosaicSelectionCoordinator(
        parent=model,
        selection_model=model,
        mosaic_view=cast(Any, view),
        all_widgets_getter=lambda: widgets,
    )
    return model, view, coordinator


def test_anchor_set_on_select() -> None:
    widgets = [_FakeWidget("a"), _FakeWidget("b"), _FakeWidget("c")]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    assert coordinator.anchor is widgets[0]

    coordinator.select(widgets[2], clear=False)
    assert coordinator.anchor is widgets[2]


def test_anchor_set_on_deselect() -> None:
    widgets = [_FakeWidget("a"), _FakeWidget("b")]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    coordinator.select(widgets[1], clear=False)
    coordinator.deselect(widgets[0])
    assert coordinator.anchor is widgets[0]


def test_anchor_preserved_by_select_range() -> None:
    widgets = [_FakeWidget(x) for x in "abcde"]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    coordinator.select_range(widgets[0], widgets[2])
    # Anchor must still point to the original item, not the range end.
    assert coordinator.anchor is widgets[0]


def test_shift_click_extends_from_anchor() -> None:
    """Shift+Click twice from the same anchor selects from that anchor each time."""
    widgets = [_FakeWidget(x) for x in "abcde"]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    coordinator.select_range(widgets[0], widgets[4])
    assert model.selected == widgets  # all five

    # Second Shift+Click closer in — range shrinks, anchor stays at widgets[0].
    coordinator.select_range(widgets[0], widgets[2])
    assert model.selected == widgets[:3]
    assert coordinator.anchor is widgets[0]


def test_ctrl_shift_adds_range() -> None:
    """Ctrl+Shift+Click unions the new range with the existing selection."""
    widgets = [_FakeWidget(x) for x in "abcde"]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    coordinator.select(widgets[2], clear=False)  # anchor = widgets[2]
    coordinator.select_range(widgets[2], widgets[4], add=True)
    # widgets[0] from the earlier Ctrl+click plus widgets[2..4] from the range.
    assert widgets[0] in model.selected
    assert widgets[2] in model.selected
    assert widgets[4] in model.selected


def test_shift_arrow_extends_selection() -> None:
    """Shift+Arrow adds the next item to the selection without moving the anchor."""
    widgets = [_FakeWidget(x) for x in "abcd"]
    model, view, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)  # anchor = widgets[0]

    handled = coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=4,
        activate_callback=lambda w: None,
        shift=True,
    )

    assert handled is True
    assert model.selected == [widgets[0], widgets[1]]
    assert coordinator.anchor is widgets[0]
    assert view.ensure_visible_calls == [widgets[1]]


def test_shift_arrow_shrinks_when_past_anchor() -> None:
    """Shift+Arrow back past the anchor reverses the range direction."""
    widgets = [_FakeWidget(x) for x in "abcde"]
    model, _, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[2], clear=True)  # anchor = widgets[2] (index 2)
    # Extend right twice → [2,3,4]
    coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=5,
        activate_callback=lambda w: None,
        shift=True,
    )
    coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=5,
        activate_callback=lambda w: None,
        shift=True,
    )
    assert model.selected == [widgets[2], widgets[3], widgets[4]]

    # Shift+Left ×4: nav cursor travels 4→3→2→1→0, crossing the anchor;
    # the range inverts to [anchor=2 … nav=0] = [0,1,2].
    for _ in range(4):
        coordinator.select_relative(
            key=QtCore.Qt.Key.Key_Left,
            columns=5,
            activate_callback=lambda w: None,
            shift=True,
        )
    assert model.selected == [widgets[0], widgets[1], widgets[2]]
    assert coordinator.anchor is widgets[2]


def test_plain_arrow_after_shift_navigates_from_nav_cursor() -> None:
    """Plain arrow after a Shift+Arrow session navigates from the live end."""
    widgets = [_FakeWidget(x) for x in "abcd"]
    model, view, coordinator = _make_coordinator(widgets)

    coordinator.select(widgets[0], clear=True)
    # Shift+Right twice: nav cursor moves to widgets[2], anchor stays at widgets[0].
    coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=4,
        activate_callback=lambda w: None,
        shift=True,
    )
    coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=4,
        activate_callback=lambda w: None,
        shift=True,
    )
    assert model.selected == [widgets[0], widgets[1], widgets[2]]

    # Plain Right: should navigate from nav cursor (widgets[2]) → widgets[3].
    activated: list[object] = []
    coordinator.select_relative(
        key=QtCore.Qt.Key.Key_Right,
        columns=4,
        activate_callback=lambda w: activated.append(w),
    )
    assert activated == [widgets[3]]
