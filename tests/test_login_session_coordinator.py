from __future__ import annotations

import vars_gridview.ui.coordinators.login_session_coordinator as lsc


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeSessionController:
    def __init__(
        self, *, login_should_succeed: bool, failure_message: str = "boom"
    ) -> None:
        self.logged_in = _FakeSignal()
        self.login_failed = _FakeSignal()
        self._login_should_succeed = login_should_succeed
        self._failure_message = failure_message
        self.calls = []

    def login(self, raziel_url: str, username: str, password: str) -> None:
        self.calls.append((raziel_url, username, password))
        if self._login_should_succeed:
            self.logged_in.emit(object())
        else:
            self.login_failed.emit(self._failure_message)


class _FakeEventLoop:
    def __init__(self, *_args, **_kwargs) -> None:
        self._running = True

    def exec(self) -> None:
        return None

    def isRunning(self) -> bool:
        return self._running

    def quit(self) -> None:
        self._running = False


class _FakeLoginDialog:
    def __init__(self, *, should_accept: bool, credentials, raziel_url: str) -> None:
        self._should_accept = should_accept
        self.credentials = credentials
        self.raziel_url = raziel_url
        self.focused = False

    def focus_username(self) -> None:
        self.focused = True

    def exec(self) -> bool:
        return self._should_accept


def test_run_login_success_returns_username_and_updates_raziel(monkeypatch) -> None:
    monkeypatch.setattr(lsc.QtCore, "QEventLoop", _FakeEventLoop)

    session = _FakeSessionController(login_should_succeed=True)
    coordinator = lsc.LoginSessionCoordinator(parent=None, session_controller=session)

    updated = []
    username = coordinator.run_login(
        parent_widget=None,
        current_raziel_url="https://old",
        set_raziel_url=lambda value: updated.append(value),
        login_dialog_factory=lambda _parent: _FakeLoginDialog(
            should_accept=True,
            credentials=("alice", "secret"),
            raziel_url="https://new",
        ),
    )

    assert username == "alice"
    assert session.calls == [("https://new", "alice", "secret")]
    assert updated == ["https://new"]


def test_run_login_cancel_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(lsc.QtCore, "QEventLoop", _FakeEventLoop)

    session = _FakeSessionController(login_should_succeed=True)
    coordinator = lsc.LoginSessionCoordinator(parent=None, session_controller=session)

    username = coordinator.run_login(
        parent_widget=None,
        current_raziel_url="https://same",
        set_raziel_url=lambda _value: None,
        login_dialog_factory=lambda _parent: _FakeLoginDialog(
            should_accept=False,
            credentials=("alice", "secret"),
            raziel_url="https://same",
        ),
    )

    assert username is None
    assert session.calls == []


def test_run_login_failure_shows_error(monkeypatch) -> None:
    monkeypatch.setattr(lsc.QtCore, "QEventLoop", _FakeEventLoop)

    errors = []
    monkeypatch.setattr(
        lsc.QtWidgets.QMessageBox,
        "critical",
        lambda *_args, **_kwargs: errors.append(True),
    )

    session = _FakeSessionController(
        login_should_succeed=False,
        failure_message="auth failed",
    )
    coordinator = lsc.LoginSessionCoordinator(parent=None, session_controller=session)

    username = coordinator.run_login(
        parent_widget=None,
        current_raziel_url="https://same",
        set_raziel_url=lambda _value: None,
        login_dialog_factory=lambda _parent: _FakeLoginDialog(
            should_accept=True,
            credentials=("alice", "secret"),
            raziel_url="https://same",
        ),
    )

    assert username is None
    assert errors == [True]
