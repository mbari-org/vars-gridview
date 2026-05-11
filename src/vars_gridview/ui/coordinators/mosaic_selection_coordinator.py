"""Coordinator for mosaic selection and keyboard navigation behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol, cast

from PyQt6 import QtCore

from vars_gridview.controllers.selection_model import SelectionModel
from vars_gridview.ui.mosaic.mosaic_view import MosaicView

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class _MosaicViewLike(Protocol):
    def visible_widgets_in_range(
        self,
        *,
        all_widgets: list,
        begin_index: int,
        end_index: int,
    ) -> list: ...

    def ensure_widget_visible_if_needed(self, rect_widget: object) -> None: ...


class MosaicSelectionCoordinator(QtCore.QObject):
    """Own selection state transitions for mosaic rect widgets."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        selection_model: SelectionModel,
        mosaic_view: _MosaicViewLike,
        all_widgets_getter: Callable[[], list],
    ) -> None:
        super().__init__(parent)
        self._selection_model = selection_model
        self._mosaic_view = mosaic_view
        self._all_widgets_getter = all_widgets_getter

    def get_selected(self) -> list:
        return self._selection_model.selected

    def clear_selected(self) -> None:
        self._selection_model.clear()

    def select(self, rect_widget: object, *, clear: bool = True) -> None:
        all_widgets = self._all_widgets_getter()
        if rect_widget not in all_widgets:
            raise ValueError("Widget not in rect widget list")
        rect = cast("RectWidget", rect_widget)

        if clear:
            self._selection_model.set_selection([rect])
        else:
            self._selection_model.add(rect)

    def deselect(self, rect_widget: object) -> None:
        all_widgets = self._all_widgets_getter()
        if rect_widget not in all_widgets:
            raise ValueError("Widget not in rect widget list")
        self._selection_model.remove(cast("RectWidget", rect_widget))

    def select_range(self, first: object, last: object) -> None:
        all_widgets = self._all_widgets_getter()
        if first not in all_widgets:
            raise ValueError("First widget not in rect widget list")
        if last not in all_widgets:
            raise ValueError("Last widget not in rect widget list")

        first_idx = all_widgets.index(first)
        last_idx = all_widgets.index(last)
        begin_idx = min(first_idx, last_idx)
        end_idx = max(first_idx, last_idx)

        range_selection = list(
            self._mosaic_view.visible_widgets_in_range(
                all_widgets=all_widgets,
                begin_index=begin_idx,
                end_index=end_idx,
            )
        )
        self._selection_model.set_selection(range_selection)

    def update_widget_selection_flags(self, selected: list) -> None:
        selected_set = set(selected)
        for rect_widget in self._all_widgets_getter():
            is_selected = rect_widget in selected_set
            if rect_widget.is_selected != is_selected:
                rect_widget.is_selected = is_selected
                rect_widget.update()

    def select_relative(
        self,
        *,
        key: QtCore.Qt.Key,
        columns: int,
        activate_callback: Callable[[object], None],
    ) -> bool:
        all_widgets = self._all_widgets_getter()
        navigable_keys = {
            QtCore.Qt.Key.Key_Left,
            QtCore.Qt.Key.Key_Right,
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
        }
        if key not in navigable_keys:
            return False

        selected = self._selection_model.selected
        if len(selected) == 0:
            return True

        first = selected[0]
        first_idx = all_widgets.index(first)
        next_idx = MosaicView.compute_relative_index(
            current_index=first_idx,
            key=key,
            columns=columns,
            total_items=len(all_widgets),
        )
        if next_idx is None:
            return False

        self._selection_model.clear()
        next_widget = all_widgets[next_idx]
        activate_callback(next_widget)
        self._mosaic_view.ensure_widget_visible_if_needed(next_widget)
        return True


__all__ = ["MosaicSelectionCoordinator"]
