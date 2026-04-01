"""Qt thread-pool worker utilities.

This module provides thin wrappers around :class:`~PyQt6.QtCore.QRunnable`
for dispatching off-thread work and reporting results back to the GUI thread
via typed Qt signals.

Typical usage::

    task = HttpGetTask(url)
    task.signals.success.connect(on_response)
    task.signals.error.connect(on_error)
    enqueue(task)
"""

from __future__ import annotations

import traceback
from typing import Callable, TypeVar

import requests
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

    def run(self) -> None:
        """Execute the wrapped callable on the pool thread."""
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            self.signals.error.emit((type(exc), exc, tb))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class HttpGetTask(QRunnable):
    """Off-thread HTTP GET task.

    Emits :attr:`signals.success` with the :class:`~requests.Response` on HTTP
    200, or :attr:`signals.error` with the exception on any failure.

    Args:
        url: URL to fetch.
    """

    class Signals(QObject):
        """Signals for :class:`HttpGetTask`.

        Attributes:
            success: Emitted with the :class:`~requests.Response`.
            error: Emitted with the exception on failure.
            responseReceived: Alias for *success* (backward compatibility).
        """

        success = pyqtSignal(object)
        error = pyqtSignal(Exception)
        responseReceived = success  # backward-compat alias

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self.signals = HttpGetTask.Signals()

    def run(self) -> None:
        """Perform the GET request and emit the appropriate signal."""
        try:
            response = requests.get(self._url, timeout=30)
            response.raise_for_status()
            self.signals.success.emit(response)
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(exc)


__all__ = ["enqueue", "start", "Worker", "WorkerSignals", "HttpGetTask"]
