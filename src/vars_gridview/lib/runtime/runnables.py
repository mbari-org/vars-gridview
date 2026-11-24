"""Qt thread-pool worker utilities.

This module provides thin wrappers around :class:`~PyQt6.QtCore.QRunnable`
for dispatching off-thread work and reporting results back to the GUI thread
via typed Qt signals.

Typical usage::

    worker = Worker(load_payload, arg1, arg2)
    worker.signals.result.connect(on_result)
    worker.signals.error.connect(on_error)
    enqueue(worker)
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import TypeVar

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


def enqueue(runnable: QRunnable) -> None:
    """Submit *runnable* to the global :class:`~PyQt6.QtCore.QThreadPool`.

    Args:
        runnable: The task to run on a pooled thread.
    """
    QThreadPool.globalInstance().start(runnable)


# Keep old name as alias for backward compatibility.
start = enqueue


class WorkerSignals(QObject):
    """Signals emitted by a :class:`Worker` runnable.

    Attributes:
        finished: Emitted when the worker completes (success or error).
        error: Emitted with ``(exc_type, exc_value, traceback_str)`` on failure.
        result: Emitted with the return value on success.
    """

    finished = pyqtSignal()
    error = pyqtSignal(tuple)  # (type, Exception, str)
    result = pyqtSignal(object)
    # Carries the worker's callable and arguments back to the thread that
    # created it, so they are released there -- see Worker.run.
    release = pyqtSignal(object)


def _drop(_payload: object) -> None:
    """Receives a finished worker's references on the GUI thread; returning
    drops them there."""


T = TypeVar("T")


class Worker(QRunnable):
    """Generic :class:`~PyQt6.QtCore.QRunnable` that wraps a callable.

    Args:
        fn: The callable to run on a pool thread.
        *args: Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.

    Signals:
        signals.result: Emitted with the return value of *fn*.
        signals.error: Emitted as ``(type, exc, traceback_str)`` on exception.
        signals.finished: Always emitted when the run completes.
    """

    def __init__(self, fn: Callable[..., T], *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        # Connected here, on the creating (GUI) thread, so delivery is queued
        # back to it.
        self.signals.release.connect(_drop)

    def run(self) -> None:
        """Execute the wrapped callable on the pool thread.

        The callable is often a bound method of, or its arguments include, a
        Qt graphics item (a mosaic tile). QThreadPool deletes the runnable on
        the pool thread when it finishes; if the worker held the last
        reference to a tile that was removed meanwhile (new page, delete),
        the tile -- its QPixmap and Qt object -- would be destroyed off the
        GUI thread, which can crash. So the references are handed back to
        the GUI thread through a queued signal and released there.
        """
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            self.signals.error.emit((type(exc), exc, tb))
        else:
            self.signals.result.emit(result)
            del result
        finally:
            signals = self.signals
            signals.finished.emit()
            # The signals object goes too: the slots connected to it are often
            # lambdas that capture a tile, and it would otherwise be freed with
            # the runnable, here on the pool thread.
            payload = (self._fn, self._args, self._kwargs, signals)
            self._fn, self._args, self._kwargs = None, (), {}
            del self.signals  # (not "= None": that would type it Optional everywhere)
            signals.release.emit(payload)
            del payload, signals


__all__ = ["Worker", "WorkerSignals", "enqueue", "start"]
