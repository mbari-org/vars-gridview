from __future__ import annotations

from types import SimpleNamespace

from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic


class _FakeSignal:
    def __init__(self) -> None:
        self.emitted: list = []

    def emit(self, value) -> None:
        self.emitted.append(value)


class _FakeRectWidget:
    def __init__(self) -> None:
        self.hidden = False

    def hide(self) -> None:
        self.hidden = True


def _fake_image_mosaic(rect_widgets: list) -> SimpleNamespace:
    fake_self = SimpleNamespace(
        _rect_widgets=list(rect_widgets),
        n_localizations=len(rect_widgets),
        clear_selected_calls=0,
        render_calls=0,
        rect_widgets_removed=_FakeSignal(),
    )
    fake_self.clear_selected = lambda: setattr(
        fake_self, "clear_selected_calls", fake_self.clear_selected_calls + 1
    )
    fake_self.render_mosaic = lambda: setattr(
        fake_self, "render_calls", fake_self.render_calls + 1
    )
    return fake_self


def test_remove_rect_widgets_emits_removed_widgets() -> None:
    rw1, rw2, rw3 = _FakeRectWidget(), _FakeRectWidget(), _FakeRectWidget()
    fake_self = _fake_image_mosaic([rw1, rw2, rw3])

    ImageMosaic.remove_rect_widgets(fake_self, [rw2])

    assert fake_self._rect_widgets == [rw1, rw3]
    assert fake_self.n_localizations == 2
    assert fake_self.clear_selected_calls == 1
    assert fake_self.render_calls == 1
    assert fake_self.rect_widgets_removed.emitted == [[rw2]]


def test_remove_rect_widgets_skips_widgets_not_present() -> None:
    rw1, rw2 = _FakeRectWidget(), _FakeRectWidget()
    stray = _FakeRectWidget()
    fake_self = _fake_image_mosaic([rw1, rw2])

    ImageMosaic.remove_rect_widgets(fake_self, [stray])

    assert fake_self._rect_widgets == [rw1, rw2]
    assert fake_self.rect_widgets_removed.emitted == []


def test_remove_rect_widgets_noop_on_empty_input() -> None:
    rw1 = _FakeRectWidget()
    fake_self = _fake_image_mosaic([rw1])

    ImageMosaic.remove_rect_widgets(fake_self, [])

    assert fake_self._rect_widgets == [rw1]
    assert fake_self.clear_selected_calls == 0
    assert fake_self.render_calls == 0
    assert fake_self.rect_widgets_removed.emitted == []
