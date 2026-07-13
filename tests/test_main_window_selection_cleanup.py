from __future__ import annotations

from types import SimpleNamespace

from vars_gridview.ui.MainWindow import MainWindow


class _FakeImageMosaic:
    def __init__(self, rect_widgets: list) -> None:
        self._rect_widgets = list(rect_widgets)
        self.deselect_calls: list = []
        self.clear_view_calls = 0
        self.clear_selected_calls = 0

    def get_all_rect_widgets(self) -> list:
        return list(self._rect_widgets)

    def deselect(self, rect_widget) -> None:
        if rect_widget not in self._rect_widgets:
            raise ValueError("Widget not in rect widget list")
        self.deselect_calls.append(rect_widget)

    def clear_view(self) -> None:
        self.clear_view_calls += 1

    def clear_selected(self) -> None:
        self.clear_selected_calls += 1


def _fake_main_window(
    image_mosaic: _FakeImageMosaic, last_selected_rect
) -> SimpleNamespace:
    fake_self = SimpleNamespace(
        image_mosaic=image_mosaic,
        last_selected_rect=last_selected_rect,
        box_handler="stale-box-handler",
        clear_selected=lambda: None,
        _clear_detail_panels=lambda: None,
    )
    return fake_self


def test_on_rect_widgets_removed_clears_stale_last_selected_rect() -> None:
    rw = object()
    fake_self = _fake_main_window(_FakeImageMosaic([]), last_selected_rect=rw)

    MainWindow._on_rect_widgets_removed(fake_self, [rw])

    assert fake_self.last_selected_rect is None


def test_on_rect_widgets_removed_ignores_unrelated_removals() -> None:
    rw, other = object(), object()
    fake_self = _fake_main_window(_FakeImageMosaic([rw]), last_selected_rect=rw)

    MainWindow._on_rect_widgets_removed(fake_self, [other])

    assert fake_self.last_selected_rect is rw


def test_prepare_for_new_results_survives_stale_last_selected_rect() -> None:
    # Regression test: last_selected_rect can outlive the widget it points to
    # when that widget was removed from the mosaic (e.g. via delete) without
    # last_selected_rect being invalidated. _prepare_for_new_results must not
    # raise in that case.
    stale_rect = object()
    image_mosaic = _FakeImageMosaic([])  # stale_rect is no longer present
    fake_self = _fake_main_window(image_mosaic, last_selected_rect=stale_rect)

    MainWindow._prepare_for_new_results(fake_self)

    assert fake_self.last_selected_rect is None
    assert image_mosaic.deselect_calls == []  # skipped: widget already gone
    assert image_mosaic.clear_view_calls == 1


def test_prepare_for_new_results_still_deselects_live_rect() -> None:
    live_rect = object()
    image_mosaic = _FakeImageMosaic([live_rect])
    fake_self = _fake_main_window(image_mosaic, last_selected_rect=live_rect)

    MainWindow._prepare_for_new_results(fake_self)

    assert fake_self.last_selected_rect is None
    assert image_mosaic.deselect_calls == [live_rect]
