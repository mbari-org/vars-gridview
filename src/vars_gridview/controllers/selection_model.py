"""Selection model for the mosaic grid.

:class:`SelectionModel` tracks which :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
objects are currently selected and emits typed signals on changes, decoupling
selection state from the :class:`~vars_gridview.ui.mosaic.image_mosaic.ImageMosaic` widget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class SelectionModel(QObject):
    """Central store for the current tile selection.

    Maintains an ordered list of selected
    :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget` tiles.  Emits
    :attr:`selection_changed` whenever the selection is modified.

    Signals:
        selection_changed: Emitted after any selection change.  The argument
            is the new list of selected widgets.
    """

    selection_changed = pyqtSignal(list)  # list[RectWidget]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._selected: list[RectWidget] = []

    # ── Queries ────────────────────────────────────────────────────────────────

    @property
    def selected(self) -> list[RectWidget]:
        """Snapshot of the currently selected widgets (read-only)."""
        return list(self._selected)

    @property
    def count(self) -> int:
        """Number of currently selected widgets."""
        return len(self._selected)

    def is_selected(self, widget: RectWidget) -> bool:
        """Return ``True`` if *widget* is currently in the selection."""
        return widget in self._selected

    # ── Mutations ──────────────────────────────────────────────────────────────

    def set_selection(self, widgets: list[RectWidget]) -> None:
        """Replace the current selection with *widgets*.

        Args:
            widgets: New selection list (may be empty).
        """
        if self._selected == widgets:
            return
        self._selected = list(widgets)
        self.selection_changed.emit(self._selected)

    def add(self, widget: RectWidget) -> None:
        """Add *widget* to the selection (no-op if already selected).

        Args:
            widget: Widget to add.
        """
        if widget not in self._selected:
            self._selected.append(widget)
            self.selection_changed.emit(self._selected)

    def remove(self, widget: RectWidget) -> None:
        """Remove *widget* from the selection (no-op if not selected).

        Args:
            widget: Widget to remove.
        """
        if widget in self._selected:
            self._selected.remove(widget)
            self.selection_changed.emit(self._selected)

    def toggle(self, widget: RectWidget) -> None:
        """Toggle the selection state of *widget*.

        Args:
            widget: Widget to toggle.
        """
        if widget in self._selected:
            self.remove(widget)
        else:
            self.add(widget)

    def clear(self) -> None:
        """Deselect all widgets."""
        if self._selected:
            self._selected = []
            self.selection_changed.emit(self._selected)

    def select_all(self, widgets: list[RectWidget]) -> None:
        """Select all widgets in *widgets*.

        Args:
            widgets: Full list of widgets to select.
        """
        self.set_selection(widgets)


__all__ = ["SelectionModel"]
