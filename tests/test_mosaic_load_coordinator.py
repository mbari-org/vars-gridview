from __future__ import annotations

from types import SimpleNamespace

from vars_gridview.ui.coordinators import mosaic_load_coordinator as mlc


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeDialog:
    def __init__(self, *_args, **_kwargs) -> None:
        self.canceled = _FakeSignal()
        self.maximum = 0
        self.value = 0
        self.closed = False

    def setWindowTitle(self, _title: str) -> None:
        pass

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration: int) -> None:
        pass

    def setValue(self, value: int) -> None:
        self.value = value

    def setMaximum(self, maximum: int) -> None:
        self.maximum = maximum

    def show(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakeEventLoop:
    def __init__(self, *_args, **_kwargs) -> None:
        self.quit_called = False

    def exec(self) -> None:
        # Worker completion is triggered synchronously by fake thread pool start.
        pass

    def quit(self) -> None:
        self.quit_called = True


class _FakeWorker:
    def __init__(self, fn) -> None:
        self._fn = fn
        self.signals = SimpleNamespace(
            result=_FakeSignal(),
            error=_FakeSignal(),
            finished=_FakeSignal(),
        )

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit((type(exc), exc, "traceback"))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class _FakeThreadPool:
    def start(self, worker) -> None:
        worker.run()


class _FakeThreadPoolProvider:
    def __init__(self, pool) -> None:
        self._pool = pool

    def globalInstance(self):
        return self._pool


def _patch_coordinator_dependencies(monkeypatch, *, pool) -> None:
    monkeypatch.setattr(mlc.QtWidgets, "QProgressDialog", _FakeDialog)
    monkeypatch.setattr(mlc.QtCore, "QEventLoop", _FakeEventLoop)
    monkeypatch.setattr(mlc, "Worker", _FakeWorker)
    monkeypatch.setattr(mlc.QtCore, "QThreadPool", _FakeThreadPoolProvider(pool))


def test_run_stage_returns_worker_payload(monkeypatch) -> None:
    _patch_coordinator_dependencies(monkeypatch, pool=_FakeThreadPool())
    coordinator = mlc.MosaicLoadCoordinator(parent=None, dialog_parent=None)

    payload = coordinator.run_stage(
        label="Testing",
        maximum=5,
        cancelled_message="cancelled",
        worker_factory=lambda _cancel_event, progress: _emit_progress(progress),
    )

    assert payload == "done"


def _emit_progress(progress):
    progress(2, 5)
    return "done"


def test_run_stage_maps_matching_cancel_error(monkeypatch) -> None:
    _patch_coordinator_dependencies(monkeypatch, pool=_FakeThreadPool())
    coordinator = mlc.MosaicLoadCoordinator(parent=None, dialog_parent=None)

    def _factory(_cancel_event, _progress):
        raise RuntimeError("cancelled")

    try:
        coordinator.run_stage(
            label="Testing",
            maximum=1,
            cancelled_message="cancelled",
            worker_factory=_factory,
        )
    except RuntimeError as exc:
        assert str(exc) == "cancelled"
    else:
        raise AssertionError("Expected RuntimeError for cancelled stage")


def test_run_stage_raises_when_thread_pool_unavailable(monkeypatch) -> None:
    _patch_coordinator_dependencies(monkeypatch, pool=None)
    coordinator = mlc.MosaicLoadCoordinator(parent=None, dialog_parent=None)

    try:
        coordinator.run_stage(
            label="Testing",
            maximum=1,
            cancelled_message="cancelled",
            worker_factory=lambda _cancel_event, _progress: None,
        )
    except RuntimeError as exc:
        assert str(exc) == "Global thread pool unavailable"
    else:
        raise AssertionError("Expected RuntimeError when thread pool is unavailable")
