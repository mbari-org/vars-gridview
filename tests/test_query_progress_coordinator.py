from __future__ import annotations

from vars_gridview.ui.coordinators import query_progress_coordinator as qpc


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeDialog:
    def __init__(self, _parent, _title, stages) -> None:
        self.cancel_requested = _FakeSignal()
        self.stages = stages
        self.active_key = None
        self.progress = (0, 0)
        self.failed_message = None
        self.closed = False
        self.finished = False

    def show(self) -> None:
        pass

    def start_stage(self, key, *, determinate=False, maximum=0) -> None:
        self.active_key = key
        self.progress = (0, maximum)

    def update_progress(self, current, maximum) -> None:
        self.progress = (current, maximum)

    def fail_stage(self, message) -> None:
        self.failed_message = message

    def finish(self) -> None:
        self.finished = True
        self.closed = True

    def close_dialog(self) -> None:
        self.closed = True


def _make_coordinator(monkeypatch, *, status_updates, cancel_calls):
    monkeypatch.setattr(qpc, "StagedProgressDialog", _FakeDialog)
    return qpc.QueryProgressCoordinator(
        parent=None,
        dialog_parent=None,
        status_update_callback=lambda state: status_updates.append(state),
        cancel_callback=lambda: cancel_calls.append(True),
    )


def test_query_progress_lifecycle(monkeypatch) -> None:
    status_updates: list = []
    cancel_calls: list = []
    coordinator = _make_coordinator(
        monkeypatch, status_updates=status_updates, cancel_calls=cancel_calls
    )

    coordinator.on_query_started()
    assert coordinator._dialog.active_key == "count"

    coordinator.begin_stage("download")
    coordinator.on_stage_progress("localization", 3, 10)
    assert coordinator._dialog.progress == (3, 10)

    coordinator.mark_done()
    assert coordinator._dialog is None
    assert status_updates == []


def test_query_failed_shows_error_and_closes(monkeypatch) -> None:
    status_updates: list = []
    cancel_calls: list = []
    errors: list = []
    monkeypatch.setattr(
        qpc.QtWidgets.QMessageBox,
        "critical",
        lambda *_args, **_kwargs: errors.append(True),
    )
    coordinator = _make_coordinator(
        monkeypatch, status_updates=status_updates, cancel_calls=cancel_calls
    )

    coordinator.on_query_started()
    dialog = coordinator._dialog
    coordinator.on_query_failed("boom")

    assert dialog.failed_message == "boom"
    assert dialog.closed is True
    assert status_updates == [{"Status": "Query failed"}]
    assert errors == [True]
    assert coordinator._dialog is None


def test_query_cancelled_closes_without_error(monkeypatch) -> None:
    status_updates: list = []
    cancel_calls: list = []
    coordinator = _make_coordinator(
        monkeypatch, status_updates=status_updates, cancel_calls=cancel_calls
    )

    coordinator.on_query_started()
    dialog = coordinator._dialog
    coordinator.on_query_cancelled()

    assert dialog.closed is True
    assert status_updates == [{"Status": "Query cancelled"}]
    assert coordinator._dialog is None


def test_cancel_button_invokes_cancel_callback(monkeypatch) -> None:
    status_updates: list = []
    cancel_calls: list = []
    coordinator = _make_coordinator(
        monkeypatch, status_updates=status_updates, cancel_calls=cancel_calls
    )

    coordinator.on_query_started()
    coordinator._dialog.cancel_requested.emit()

    assert cancel_calls == [True]
