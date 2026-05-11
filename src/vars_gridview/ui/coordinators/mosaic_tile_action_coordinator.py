"""Coordinator for tile-level label/verify/training actions in the mosaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.ui.dialogs.concept_selection_dialog import ConceptSelectionDialog

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class MosaicTileActionCoordinator(QtCore.QObject):
    """Owns per-tile action dispatch and concept/part selection UI flow."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget | None,
        concept_provider: Callable[[], list[str]] | None,
        part_provider: Callable[[], list[str]] | None,
        label_action_callback: Callable[[RectWidget, str, str], None] | None,
        verify_action_callback: Callable[[RectWidget], None] | None,
        mark_training_action_callback: Callable[[RectWidget], None] | None,
        concept_picker: Callable[
            [QtWidgets.QWidget | None, list[str], list[str]],
            tuple[str, str | None] | None,
        ]
        | None = None,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._concept_provider = concept_provider
        self._part_provider = part_provider
        self._label_action_callback = label_action_callback
        self._verify_action_callback = verify_action_callback
        self._mark_training_action_callback = mark_training_action_callback
        self._concept_picker = concept_picker or self._default_concept_picker

    @staticmethod
    def _default_concept_picker(
        parent: QtWidgets.QWidget | None,
        concepts: list[str],
        parts: list[str],
    ) -> tuple[str, str | None] | None:
        return ConceptSelectionDialog.pick_concept_and_part(
            parent=parent,
            concepts=concepts,
            parts=parts,
        )

    def handle_label_action(self, rect: RectWidget) -> None:
        concepts = (
            self._concept_provider() if self._concept_provider is not None else []
        )
        parts = self._part_provider() if self._part_provider is not None else []
        selected = self._concept_picker(self._dialog_parent, concepts, parts)
        if selected is None:
            return

        concept, part = selected
        part = part or "self"
        if self._label_action_callback is not None:
            self._label_action_callback(rect, concept, part)
            return

        LOGGER.error("Label action callback is not configured for tile action")

    def handle_verify_action(self, rect: RectWidget) -> None:
        if self._verify_action_callback is not None:
            self._verify_action_callback(rect)
            return
        LOGGER.error("Verify action callback is not configured for tile action")

    def handle_mark_training_action(self, rect: RectWidget) -> None:
        if self._mark_training_action_callback is not None:
            self._mark_training_action_callback(rect)
            return
        LOGGER.error("Mark-training action callback is not configured for tile action")


__all__ = ["MosaicTileActionCoordinator"]
