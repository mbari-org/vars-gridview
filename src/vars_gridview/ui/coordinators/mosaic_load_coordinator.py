"""UI coordinator for staged mosaic loading workflows.

Owns worker lifecycle orchestration for cancellable stages that need:
- a modal progress dialog,
- worker-thread execution,
- thread-safe progress updates back to UI,
- result/error handoff to the caller.
"""

from __future__ import annotations

from threading import Event
from typing import Callable

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.runnables import Worker


class MosaicLoadCoordinator(QtCore.QObject):
    """Run cancellable loading stages with UI-owned progress dialogs."""

    stage_progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._active_dialog: QtWidgets.QProgressDialog | None = None
        self.stage_progress.connect(self._on_stage_progress)

    def run_stage(
        self,
        *,
        label: str,
        maximum: int,
        cancelled_message: str,
        worker_factory: Callable[[Event, Callable[[int, int], None]], object],
    ) -> object | None:
        """Run one stage and return worker result payload (if any)."""
        dialog = QtWidgets.QProgressDialog(
            label,
            "Cancel",
            0,
            max(0, maximum),
            self._dialog_parent,
        )
        dialog.setWindowTitle("Loading")
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setValue(0)
        dialog.show()

        self._active_dialog = dialog
        cancel_event = Event()
        dialog.canceled.connect(cancel_event.set)

        result_holder: dict[str, object] = {}
        error_holder: dict[str, tuple] = {}
        wait_loop = QtCore.QEventLoop(self)

        worker = Worker(lambda: worker_factory(cancel_event, self.stage_progress.emit))
        worker.signals.result.connect(
            lambda payload: result_holder.setdefault("value", payload)
        )
        worker.signals.error.connect(lambda err: error_holder.setdefault("value", err))
        worker.signals.finished.connect(wait_loop.quit)

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            dialog.close()
            self._active_dialog = None
            raise RuntimeError("Global thread pool unavailable")

        pool.start(worker)
        wait_loop.exec()

        try:
            if "value" in error_holder:
                err = error_holder["value"]
                exc = err[1]
                if isinstance(exc, RuntimeError) and str(exc) == cancelled_message:
                    raise RuntimeError(cancelled_message) from exc
                raise exc
            return result_holder.get("value", None)
        finally:
            dialog.close()
            self._active_dialog = None

    @QtCore.pyqtSlot(int, int)
    def _on_stage_progress(self, current: int, total: int) -> None:
        dialog = self._active_dialog
        if dialog is None:
            return
        dialog.setMaximum(max(0, total))
        dialog.setValue(max(0, min(current, total)))


__all__ = ["MosaicLoadCoordinator"]
