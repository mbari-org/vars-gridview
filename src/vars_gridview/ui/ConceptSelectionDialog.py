from typing import Optional, Tuple

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.m3.operations import get_kb_concepts, get_kb_parts
from vars_gridview.lib.log import LOGGER


class ConceptSelectionDialog(QtWidgets.QDialog):
    """
    Dialog for selecting concepts and parts with autocomplete functionality.
    """

    def __init__(
        self, parent=None, title: str = "Select Concept", include_part: bool = False
    ):
        super().__init__(parent=parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        self.include_part = include_part
        self.selected_concept = None
        self.selected_part = None

        # Get available concepts and parts
        try:
            self.concepts = list(get_kb_concepts().keys())
            if include_part:
                self.parts = get_kb_parts()
        except Exception as e:
            LOGGER.error(f"Failed to load concepts/parts: {e}")
            self.concepts = []
            self.parts = [] if include_part else None
            QtWidgets.QMessageBox.warning(
                self,
                "Connection Error",
                f"Failed to load concepts/parts from server:\n{str(e)}\n\nPlease check your connection and try again.",
            )

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
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

    def _setup_connections(self):
        """Set up signal connections."""
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

    def _on_accept(self):
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
    def pick_concept(cls, parent=None) -> Optional[str]:
        """
        Show a dialog to pick a concept.

        Args:
            parent: The parent widget.

        Returns:
            The selected concept name, or None if cancelled.
        """
        dialog = cls(parent, "Select Concept", include_part=False)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_concept
        return None

    @classmethod
    def pick_concept_and_part(cls, parent=None) -> Optional[Tuple[str, Optional[str]]]:
        """
        Show a dialog to pick a concept and optionally a part.

        Args:
            parent: The parent widget.

        Returns:
            A tuple of (concept, part) where part can be None, or None if cancelled.
        """
        dialog = cls(parent, "Select Concept and Part", include_part=True)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return (dialog.selected_concept, dialog.selected_part)
        return None
