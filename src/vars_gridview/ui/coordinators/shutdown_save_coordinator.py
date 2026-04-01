"""Coordinator for async shutdown-save workflow in MainWindow."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER

from vars_gridview.lib.runtime.runnables import Worker


class ShutdownSaveCoordinator(QtCore.QObject):
    """Own close-time save dialog lifecycle and worker dispatch."""

    def __init__(self, *, parent: QtCore.QObject, dialog_parent: QtWidgets.QWidget):
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._in_progress = False
        self._dialog: QtWidgets.QProgressDialog | None = None
        self._allow_close_once = False
        self._request_close_callback: Optional[Callable[[], None]] = None
        self._clear_dirty_callback: Optional[Callable[[set], None]] = None

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    def consume_allow_close_once(self) -> bool:
        """Return and clear one-shot shutdown bypass state."""
        allow = self._allow_close_once
        self._allow_close_once = False
        return allow

    def handle_close_event(
        self,
        *,
        event: QtGui.QCloseEvent,
        loaded: bool,
        box_handler,
        save_callable: Callable[[list], object],
        request_close: Callable[[], None],
    ) -> bool:
        """Handle close-time save orchestration.

        Returns True when this coordinator takes ownership of close handling.
        """
        if not loaded or box_handler is None:
            return False

        event.ignore()
        if self._in_progress:
            return True

        dirty_associations = box_handler.get_dirty_associations()
        if not dirty_associations:
            self._allow_close_once = True
            request_close()
            return True

        self._request_close_callback = request_close
        self._clear_dirty_callback = box_handler.clear_dirty_for
        self.start(
            save_callable=lambda: save_callable(dirty_associations),
            on_result=self._on_close_save_ready_from_worker,
            on_error=self._on_close_save_failed,
            on_finished=self._on_close_save_finished,
        )
        return True

    def start(
        self,
        *,
        save_callable: Callable[[], object],
        on_result: Callable[[object], None],
        on_error: Callable[[tuple], None],
        on_finished: Callable[[], None],
    ) -> bool:
        """Start shutdown save workflow if not already in progress."""
        if self._in_progress:
            return False
        self._in_progress = True

        self._dialog = QtWidgets.QProgressDialog(
            "Saving localizations before exit...",
            None,
            0,
            0,
            self._dialog_parent,
        )
        self._dialog.setWindowTitle("Saving")
        self._dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._dialog.setMinimumDuration(0)
        self._dialog.show()

        worker = Worker(save_callable)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(lambda: self._finish(on_finished))

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            on_error((RuntimeError, RuntimeError("No thread pool"), ""))
            self._finish(on_finished)
            return False

        pool.start(worker)
        return True

    def _finish(self, callback: Callable[[], None]) -> None:
        self._in_progress = False
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None
        callback()

    @QtCore.pyqtSlot(object)
    def _on_close_save_ready_from_worker(self, saved_association_uuids: object) -> None:
        if self._clear_dirty_callback is not None and isinstance(
            saved_association_uuids, set
        ):
            self._clear_dirty_callback(saved_association_uuids)

        self._allow_close_once = True
        if self._request_close_callback is not None:
            self._request_close_callback()

    @QtCore.pyqtSlot(tuple)
    def _on_close_save_failed(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error("Could not save localizations during shutdown: %s", message)
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Error",
            f"An error occurred while saving localizations: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_close_save_finished(self) -> None:
        self._request_close_callback = None
        self._clear_dirty_callback = None


__all__ = ["ShutdownSaveCoordinator"]
