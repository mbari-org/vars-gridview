"""The unhandled-exception hook must not run a nested event loop."""

from __future__ import annotations

import sys

from PyQt6 import QtCore, QtWidgets

from vars_gridview.__main__ import install_exception_hook


def test_hook_shows_dialog_without_blocking_and_one_at_a_time(monkeypatch) -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    shown = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "exec",
        lambda self: (_ for _ in ()).throw(AssertionError("exec() blocks")),
    )
    monkeypatch.setattr(QtWidgets.QMessageBox, "show", lambda self: shown.append(self))
    old_hook = sys.excepthook
    try:
        install_exception_hook()

        def boom() -> None:
            raise RuntimeError("from a singleShot callback")

        for _ in range(2):
            QtCore.QTimer.singleShot(0, boom)
        deadline = QtCore.QDeadlineTimer(2000)
        while len(shown) < 1 and not deadline.hasExpired():
            app.processEvents()
        for _ in range(5):
            app.processEvents()
        assert len(shown) == 1  # the second error waits for the first dialog
        shown[0].done(0)  # closing it lets the next error show a dialog
        QtCore.QTimer.singleShot(0, boom)
        for _ in range(5):
            app.processEvents()
        assert len(shown) == 2
        for box in shown:
            box.close()
    finally:
        sys.excepthook = old_hook
