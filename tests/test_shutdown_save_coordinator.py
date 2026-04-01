from __future__ import annotations

from vars_gridview.ui.coordinators import shutdown_save_coordinator as ssc


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
        self.closed = False

    def setWindowTitle(self, _title: str) -> None:
        pass

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration: int) -> None:
        pass

    def show(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakeWorker:
    def __init__(self, fn) -> None:
        self._fn = fn
        self.signals = type(
            "Signals",
            (),
            {
                "result": _FakeSignal(),
                "error": _FakeSignal(),
                "finished": _FakeSignal(),
            },
        )()

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit((type(exc), exc, "trace"))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class _FakePool:
    def start(self, worker) -> None:
        worker.run()


class _FakePoolProvider:
    def __init__(self, pool) -> None:
        self._pool = pool

    def globalInstance(self):
        return self._pool


def _patch(monkeypatch, *, pool) -> None:
    monkeypatch.setattr(ssc.QtWidgets, "QProgressDialog", _FakeDialog)
    monkeypatch.setattr(ssc, "Worker", _FakeWorker)
    monkeypatch.setattr(ssc.QtCore, "QThreadPool", _FakePoolProvider(pool))


def test_start_runs_save_and_callbacks(monkeypatch) -> None:
    _patch(monkeypatch, pool=_FakePool())
    coordinator = ssc.ShutdownSaveCoordinator(parent=None, dialog_parent=None)

    seen = {"result": None, "finished": False}

    started = coordinator.start(
        save_callable=lambda: {"saved": True},
        on_result=lambda value: seen.__setitem__("result", value),
        on_error=lambda _err: None,
        on_finished=lambda: seen.__setitem__("finished", True),
    )

    assert started is True
    assert seen["result"] == {"saved": True}
    assert seen["finished"] is True
    assert coordinator.in_progress is False


def test_start_without_pool_reports_error(monkeypatch) -> None:
    _patch(monkeypatch, pool=None)
    coordinator = ssc.ShutdownSaveCoordinator(parent=None, dialog_parent=None)

    errors = []
    finished = []

    started = coordinator.start(
        save_callable=lambda: None,
        on_result=lambda _value: None,
        on_error=lambda err: errors.append(err),
        on_finished=lambda: finished.append(True),
    )

    assert started is False
    assert errors
    assert finished == [True]
    assert coordinator.in_progress is False
