from __future__ import annotations

from types import SimpleNamespace

from vars_gridview.controllers.session_controller import SessionController


def _fake_context() -> object:
    return SimpleNamespace(
        vars_kb_server=object(),
        vampire_squid=object(),
        annosaurus=object(),
        skimmer=object(),
        beholder=object(),
    )


def test_on_auth_result_sets_services_and_emits_logged_in() -> None:
    ctrl = SessionController()
    context = _fake_context()
    emitted = []
    ctrl.logged_in.connect(lambda ctx: emitted.append(ctx))

    ctrl._on_auth_result(context)  # type: ignore[arg-type]

    assert ctrl.context is context
    assert ctrl.is_logged_in is True
    assert ctrl.knowledge_base is not None
    assert ctrl.annotations is not None
    assert ctrl.roi is not None
    assert emitted == [context]


def test_on_auth_error_emits_formatted_message() -> None:
    ctrl = SessionController()
    errors = []
    ctrl.login_failed.connect(lambda message: errors.append(message))

    ctrl._on_auth_error((RuntimeError, RuntimeError("boom"), "trace"))

    assert errors == ["RuntimeError: boom"]


def test_logout_clears_state_and_emits_logged_out() -> None:
    ctrl = SessionController()
    context = _fake_context()
    emitted = []
    ctrl.logged_out.connect(lambda: emitted.append("logged_out"))

    ctrl._on_auth_result(context)  # type: ignore[arg-type]
    ctrl.logout()

    assert ctrl.context is None
    assert ctrl.is_logged_in is False
    assert ctrl.knowledge_base is None
    assert ctrl.annotations is None
    assert ctrl.roi is None
    assert emitted == ["logged_out"]
