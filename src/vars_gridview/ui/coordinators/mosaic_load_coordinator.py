"""UI coordinator for staged mosaic loading workflows.

Owns worker lifecycle orchestration for cancellable stages that need:
- worker-thread execution,
- thread-safe progress updates relayed to a caller-owned progress display,
- result/error handoff to the caller.
"""

from __future__ import annotations

from threading import Event
from typing import Callable

from PyQt6 import QtCore

from vars_gridview.lib.runtime.runnables import Worker


class MosaicLoadCoordinator(QtCore.QObject):
    """Run cancellable loading stages, relaying progress via a Qt signal.

    Does not own any UI presentation itself; callers connect to
    :attr:`stage_progress` to drive their own shared progress display.
    """

    stage_progress = QtCore.pyqtSignal(int, int)

    def __init__(self, *, parent: QtCore.QObject) -> None:
        super().__init__(parent)

    def run_stage(
        self,
        *,
        cancelled_message: str,
        cancel_event: Event,
        worker_factory: Callable[[Event, Callable[[int, int], None]], object],
    ) -> object | None:
        """Run one stage and return worker result payload (if any)."""
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
            raise RuntimeError("Global thread pool unavailable")

        pool.start(worker)
        wait_loop.exec()

        if "value" in error_holder:
            err = error_holder["value"]
            exc = err[1]
            if isinstance(exc, RuntimeError) and str(exc) == cancelled_message:
                raise RuntimeError(cancelled_message) from exc
            raise exc
        return result_holder.get("value", None)


__all__ = ["MosaicLoadCoordinator"]
