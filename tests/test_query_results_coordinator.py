from __future__ import annotations

from threading import Event
from types import SimpleNamespace

from vars_gridview.ui.coordinators.query_results_coordinator import (
    QueryResultsCoordinator,
)


class _FakeSortDialog:
    def clear(self) -> None:
        pass


class _FakeImageMosaic:
    def __init__(self) -> None:
        self.populate_calls: list = []
        self.hide_labeled = False
        self.hide_unlabeled = False
        self.hide_training = False
        self.hide_nontraining = False
        self.sort_calls: list = []
        self.render_calls = 0

    def populate(self, query_headers, query_rows, *, cancel_event) -> None:
        self.populate_calls.append((query_headers, query_rows))

    def sort_rect_widgets(self, method) -> None:
        self.sort_calls.append(method)

    def render_mosaic(self) -> None:
        self.render_calls += 1


def _make_coordinator(image_mosaic, kb_service=None) -> QueryResultsCoordinator:
    return QueryResultsCoordinator(
        parent=None,
        image_mosaic=image_mosaic,
        sort_dialog_getter=lambda: _FakeSortDialog(),
        roi_detail_graphics_view=None,
        settings=SimpleNamespace(),
        kb_service_getter=lambda: kb_service,
        annotation_service_getter=lambda: None,
        change_concept_callback=lambda *_args: None,
        change_part_callback=lambda *_args: None,
        delete_callback=lambda *_args: None,
    )


def test_apply_query_results_skips_render_when_cancelled() -> None:
    image_mosaic = _FakeImageMosaic()
    coordinator = _make_coordinator(image_mosaic)
    cancel_event = Event()
    cancel_event.set()

    result = coordinator.apply_query_results(
        query_headers=["a"],
        query_rows=[["1"]],
        hide_labeled=False,
        hide_unlabeled=False,
        hide_training=False,
        hide_nontraining=False,
        cancel_event=cancel_event,
    )

    assert result is None
    assert image_mosaic.populate_calls == [(["a"], [["1"]])]
    assert image_mosaic.render_calls == 0
    assert image_mosaic.sort_calls == []


def test_apply_query_results_renders_when_not_cancelled() -> None:
    image_mosaic = _FakeImageMosaic()
    coordinator = _make_coordinator(image_mosaic, kb_service=None)

    result = coordinator.apply_query_results(
        query_headers=["a"],
        query_rows=[["1"]],
        hide_labeled=False,
        hide_unlabeled=False,
        hide_training=False,
        hide_nontraining=False,
        cancel_event=Event(),
    )

    # kb_service is unavailable in this stub, so the coordinator still returns
    # None, but only after rendering -- unlike the cancelled case above.
    assert result is None
    assert image_mosaic.render_calls == 1
    assert len(image_mosaic.sort_calls) == 1
