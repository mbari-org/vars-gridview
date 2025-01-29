from PyQt6 import QtCore, QtWidgets


class ClickableLineEdit(QtWidgets.QLineEdit):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, a0):
        if a0.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        return super().mousePressEvent(a0)


class FileSelectionLineEdit(ClickableLineEdit):
    """
    File selection line edit. When clicked, opens a file selection dialog. Not editable directly.
    """

    def __init__(self, filter: str = "All Files (*)", parent=None):
        super().__init__(parent=parent)

        self._filter = filter

        self.setReadOnly(True)
        self.setPlaceholderText("Click to select file...")
        self.clicked.connect(self._open_select_dialog)

    @QtCore.pyqtSlot()
    def _open_select_dialog(self):
        """
        Open the file select dialog and update the line edit text.
        """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, filter=self.filter)
        if file_path:
            self.setText(file_path)

    @property
    def filter(self) -> str:
        """
        Get the filter.

        Returns:
            The filter string.
        """
        return self._filter


class DirectorySelectionLineEdit(ClickableLineEdit):
    """
    Directory selection line edit. When clicked, opens a directory selection dialog. Not editable directly.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setReadOnly(True)
        self.setPlaceholderText("Click to select directory...")
        self.clicked.connect(self._open_select_dialog)

    @QtCore.pyqtSlot()
    def _open_select_dialog(self):
        """
        Open the directory select dialog and update the line edit text.
        """
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self)
        if dir_path:
            self.setText(dir_path)
