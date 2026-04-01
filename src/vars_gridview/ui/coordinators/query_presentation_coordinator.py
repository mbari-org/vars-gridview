"""Coordinator for query progress UI and failure presentation."""

from __future__ import annotations

from typing import Callable

from PyQt6 import QtCore, QtWidgets


class QueryPresentationCoordinator(QtCore.QObject):
    """Own query progress dialog lifecycle and user-facing query messages."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
        status_update_callback: Callable[[dict[str, str]], None],
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._status_update_callback = status_update_callback
        self._query_progress_dialog: QtWidgets.QProgressDialog | None = None

    def on_query_started(self) -> None:
        if self._query_progress_dialog is not None:
            return
        self._query_progress_dialog = QtWidgets.QProgressDialog(
            "Starting query...",
            None,
            0,
            6,
            self._dialog_parent,
        )
        self._query_progress_dialog.setWindowTitle("Loading Query")
        self._query_progress_dialog.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self._query_progress_dialog.setMinimumDuration(0)
        self._query_progress_dialog.setValue(0)
        self._query_progress_dialog.show()

    def on_query_progress(self, message: str, step: int, total_steps: int) -> None:
        dialog = self._query_progress_dialog
        if dialog is None:
            return
        if dialog.maximum() != total_steps:
            dialog.setMaximum(total_steps)
        dialog.setLabelText(message)
        dialog.setValue(max(0, min(step, total_steps)))

    def on_query_failed(self, message: str) -> None:
        self.close_progress_dialog()
        self._status_update_callback({"Status": "Query failed"})
        QtWidgets.QMessageBox.critical(self._dialog_parent, "Query Failed", message)

    def mark_rendering(self) -> None:
        dialog = self._query_progress_dialog
        if dialog is None:
            return
        dialog.setLabelText("Rendering mosaic...")
        dialog.setValue(5)

    def mark_done(self) -> None:
        dialog = self._query_progress_dialog
        if dialog is None:
            return
        dialog.setLabelText("Done")
        dialog.setValue(6)
        self.close_progress_dialog()

    def close_progress_dialog(self) -> None:
        if self._query_progress_dialog is not None:
            self._query_progress_dialog.close()
            self._query_progress_dialog = None


__all__ = ["QueryPresentationCoordinator"]
