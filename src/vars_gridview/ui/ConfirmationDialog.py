"""Simple yes/no confirmation dialog."""

from __future__ import annotations

from PyQt6 import QtWidgets

from vars_gridview.ui.style import UiDimensions


class ConfirmationDialog(QtWidgets.QDialog):
    """Modal confirmation dialog with Yes and No buttons.

    Prefer the :meth:`confirm` class-method for one-shot confirmation.
    """

    def __init__(self, parent: QtWidgets.QWidget | None, title: str, text: str) -> None:
        super().__init__(parent=parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(UiDimensions.DIALOG_MIN_WIDTH)

        self._text = QtWidgets.QLabel(text)

        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Yes
            | QtWidgets.QDialogButtonBox.StandardButton.No
        )
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Yes
        ).pressed.connect(self.accept)
        self._button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.No
        ).pressed.connect(self.reject)

        self._arrange()

    def _arrange(self):
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self._text)
        layout.addWidget(self._button_box)

        self.setLayout(layout)

    @classmethod
    def confirm(
        cls,
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
    ) -> bool:
        """Show a confirmation dialog and return the user's choice.

        Args:
            parent: Parent widget (may be ``None``).
            title: Dialog window title.
            text: Message displayed inside the dialog.

        Returns:
            ``True`` if the user clicked *Yes*, ``False`` otherwise.
        """
        dialog = cls(parent, title, text)
        return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
