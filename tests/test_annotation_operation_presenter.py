"""A failed label keeps the selection when nothing was written."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6 import QtWidgets

from vars_gridview.ui.coordinators.annotation_operation_presenter import (
    AnnotationOperationPresenter,
)

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _ActionState:
    def __init__(self, pending: str | None) -> None:
        self.pending_action = pending

    def clear_pending(self) -> None:
        self.pending_action = None

    def consume_pending_deleted_rects(self) -> list:
        return []


class _Mosaic:
    def __init__(self) -> None:
        self.cleared = 0

    def get_all_rect_widgets(self) -> list:
        return []

    def clear_selected(self) -> None:
        self.cleared += 1

    def render_mosaic(self) -> None:
        pass


@pytest.fixture
def presenter(monkeypatch):
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", lambda *a, **k: None)
    mosaic = _Mosaic()
    state = _ActionState("label")
    p = AnnotationOperationPresenter(
        parent=None,
        image_mosaic=mosaic,
        roi_graphics_view=SimpleNamespace(),
        clear_detail_panels_callback=lambda: None,
        status_update_callback=lambda _status: None,
        box_handler_getter=lambda: None,
        action_state=state,
    )
    return SimpleNamespace(p=p, mosaic=mosaic, state=state)


def test_failure_before_start_keeps_selection(presenter) -> None:
    # e.g. "'Sebastes melanop' is not a concept in the knowledge base"
    presenter.p.on_failed("not a concept")
    assert presenter.mosaic.cleared == 0
    assert presenter.state.pending_action is None


def test_failure_part_way_refreshes(presenter) -> None:
    presenter.p.on_started("Labelling 800 localizations")
    presenter.p.on_failed("HTTP 500")
    assert presenter.mosaic.cleared == 1


def test_started_flag_resets_between_operations(presenter) -> None:
    presenter.p.on_started("Labelling 3 localizations")
    presenter.p.on_finished()
    assert presenter.mosaic.cleared == 1

    presenter.state.pending_action = "label"
    presenter.p.on_failed("not a concept")  # next one fails before starting
    assert presenter.mosaic.cleared == 1
