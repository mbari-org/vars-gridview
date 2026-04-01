"""Dialog for selecting VARS concepts and parts with auto-complete support."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.ui.style import UiDimensions


class ConceptSelectionDialog(QtWidgets.QDialog):
    """
    Dialog for selecting concepts and parts with autocomplete functionality.
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        title: str = "Select Concept",
        include_part: bool = False,
        concepts: list[str] | None = None,
        parts: list[str] | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(UiDimensions.DIALOG_MIN_WIDTH)

        self.include_part = include_part
        self.selected_concept = None
        self.selected_part = None

        self.concepts = list(concepts or [])
        self.parts = list(parts or []) if include_part else None
        if not self.concepts:
            LOGGER.warning("Concept selection opened with no concept options")

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout()

        # Concept selection
        concept_label = QtWidgets.QLabel("Concept:")
        self.concept_line_edit = QtWidgets.QLineEdit()
        self.concept_completer = QtWidgets.QCompleter(self.concepts)
        self.concept_completer.setCaseSensitivity(
            QtCore.Qt.CaseSensitivity.CaseInsensitive
        )
        self.concept_completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.concept_completer.setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self.concept_line_edit.setCompleter(self.concept_completer)

        layout.addWidget(concept_label)
        layout.addWidget(self.concept_line_edit)

        # Part selection (optional)
        if self.include_part:
            part_label = QtWidgets.QLabel("Part (optional):")
            self.part_line_edit = QtWidgets.QLineEdit()
            self.part_completer = QtWidgets.QCompleter(self.parts)
            self.part_completer.setCaseSensitivity(
                QtCore.Qt.CaseSensitivity.CaseInsensitive
            )
            self.part_completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
            self.part_completer.setCompletionMode(
                QtWidgets.QCompleter.CompletionMode.PopupCompletion
            )
            self.part_line_edit.setCompleter(self.part_completer)

            layout.addWidget(part_label)
            layout.addWidget(self.part_line_edit)

        # Button box
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def _setup_connections(self) -> None:
        """Set up signal connections."""
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

    def _on_accept(self) -> None:
        """Handle OK button click."""
        concept_text = self.concept_line_edit.text().strip()

        # Validate concept
        if not concept_text:
            QtWidgets.QMessageBox.warning(
                self, "Invalid Input", "Concept must be specified."
            )
            return

        if concept_text not in self.concepts:
            QtWidgets.QMessageBox.warning(
                self, "Invalid Input", f"'{concept_text}' is not a valid concept."
            )
            return

        self.selected_concept = concept_text

        # Validate part (if applicable)
        if self.include_part:
            part_text = self.part_line_edit.text().strip()
            if part_text:
                if part_text not in self.parts:
                    QtWidgets.QMessageBox.warning(
                        self, "Invalid Input", f"'{part_text}' is not a valid part."
                    )
                    return
                self.selected_part = part_text
            else:
                self.selected_part = None

        self.accept()

    @classmethod
    def pick_concept(
        cls,
        parent: QtWidgets.QWidget | None = None,
        concepts: list[str] | None = None,
    ) -> str | None:
        """Show a dialog to pick a concept.

        Args:
            parent: Optional parent widget.

        Returns:
            The selected concept name, or ``None`` if cancelled.
        """
        dialog = cls(
            parent,
            "Select Concept",
            include_part=False,
            concepts=concepts,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_concept
        return None

    @classmethod
    def pick_concept_and_part(
        cls,
        parent: QtWidgets.QWidget | None = None,
        concepts: list[str] | None = None,
        parts: list[str] | None = None,
    ) -> tuple[str, str | None] | None:
        """Show a dialog to pick a concept and optionally a part.

        Args:
            parent: Optional parent widget.

        Returns:
            A ``(concept, part)`` tuple where *part* may be ``None``, or
            ``None`` if the dialog was cancelled.
        """
        dialog = cls(
            parent,
            "Select Concept and Part",
            include_part=True,
            concepts=concepts,
            parts=parts,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return (dialog.selected_concept, dialog.selected_part)
        return None
