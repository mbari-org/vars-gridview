"""Paging while edited boxes are saving: one save, and only the latest
navigation runs after it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.MainWindow import MainWindow

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _HeldPool:
    def __init__(self) -> None:
        self.workers: list = []

    def start(self, worker) -> None:
        self.workers.append(worker)


class _BoxHandler:
    def __init__(self) -> None:
        self.dirty = ["a1", "a2"]

    def get_dirty_associations(self) -> list:
        return list(self.dirty)

    def clear_dirty_for(self, uuids: set) -> None:
        self.dirty = [d for d in self.dirty if d not in uuids]


@pytest.fixture
def window(monkeypatch):
    pool = _HeldPool()
    monkeypatch.setattr(QtCore.QThreadPool, "globalInstance", lambda: pool)
    status = SimpleNamespace(showMessage=lambda *a: None, clearMessage=lambda: None)
    errors: list = []
    saves: list = []

    def save(dirty):
        saves.append(dirty)
        return set(dirty)

    w = SimpleNamespace(
        box_handler=_BoxHandler(),
        _dirty_save_running=False,
        _after_dirty_save=None,
        _dirty_association_save=SimpleNamespace(save_dirty_associations_worker=save),
        _notify_error=lambda *a: errors.append(a),
        statusBar=lambda: status,
    )
    return SimpleNamespace(w=w, pool=pool, saves=saves, errors=errors)


def _navigate(w, proceed) -> None:
    MainWindow._save_dirty_boxes_then(w, proceed)


def test_double_click_saves_once_and_pages_once(window) -> None:
    pages: list[str] = []
    _navigate(window.w, lambda: pages.append("next"))
    _navigate(window.w, lambda: pages.append("next"))
    assert len(window.pool.workers) == 1

    window.pool.workers[0].run()
    assert window.saves == [["a1", "a2"]]
    assert pages == ["next"]
    assert not window.w._dirty_save_running


def test_latest_request_wins(window) -> None:
    pages: list[str] = []
    _navigate(window.w, lambda: pages.append("next"))
    _navigate(window.w, lambda: pages.append("query"))
    window.pool.workers[0].run()
    assert pages == ["query"]


def test_failed_save_keeps_results(window) -> None:
    def boom(_dirty):
        raise ConnectionError("VARS down")

    window.w._dirty_association_save.save_dirty_associations_worker = boom
    pages: list[str] = []
    _navigate(window.w, lambda: pages.append("next"))
    _navigate(window.w, lambda: pages.append("next"))
    window.pool.workers[0].run()
    assert pages == []
    assert len(window.errors) == 1
    assert not window.w._dirty_save_running
    assert window.w._after_dirty_save is None


def test_nothing_dirty_goes_straight_on(window) -> None:
    window.w.box_handler.dirty = []
    pages: list[str] = []
    _navigate(window.w, lambda: pages.append("next"))
    assert pages == ["next"]
    assert window.pool.workers == []
