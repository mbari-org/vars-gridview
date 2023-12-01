from PyQt6 import QtWidgets


class ConfirmationDialog(QtWidgets.QDialog):
    """
    Confirmation dialog.
    """

    def __init__(self, parent, title: str, text: str):
        super().__init__(parent=parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

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
    def confirm(cls, parent, title: str, text: str) -> bool:
        """
        Show a confirmation dialog.

        Args:
            parent: The parent widget.
            title: The title of the dialog.
            text: The text to display.

        Returns:
            True if the user confirmed, False otherwise.
        """
        dialog = cls(parent, title, text)
        return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
