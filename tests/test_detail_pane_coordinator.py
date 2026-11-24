from types import SimpleNamespace

import numpy as np
from PyQt6 import QtWidgets

from vars_gridview.lib.vision.display_adjust import ColourCorrector, DisplayAdjustment
from vars_gridview.ui.coordinators.detail_pane_coordinator import DetailPaneCoordinator


class _FakeBoxHandler:
    def __init__(self, result: bool):
        self.result = result
        self.calls = []

    def retarget_annotations_for_same_source(self, rect):
        self.calls.append(rect)
        return self.result


def test_update_overlays_for_same_source_uses_box_handler() -> None:
    rect = SimpleNamespace(localization_index=1)
    box_handler = _FakeBoxHandler(True)

    coordinator = DetailPaneCoordinator(
        box_handler_getter=lambda: box_handler,
        selected_rect_getter=lambda: None,
    )

    assert coordinator.update_overlays_for_same_source(rect) is True
    assert box_handler.calls == [rect]


def test_update_overlays_for_same_source_without_box_handler() -> None:
    rect = SimpleNamespace(localization_index=1)

    coordinator = DetailPaneCoordinator(
        box_handler_getter=lambda: None,
        selected_rect_getter=lambda: None,
    )

    assert coordinator.update_overlays_for_same_source(rect) is False


# -- image view work runs on workers -------------------------------------------


_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _InlinePool:
    """Runs a worker right away on this thread; counts them."""

    def __init__(self) -> None:
        self.started = 0

    def start(self, worker) -> None:
        self.started += 1
        worker.run()


class _FakeDetail:
    def __init__(self) -> None:
        self.images: list[np.ndarray] = []

    def setImage(self, image) -> None:
        self.images.append(image)


class _FakeView:
    def autoRange(self) -> None:
        pass


class _DetailBoxHandler:
    def __init__(self) -> None:
        self.roi_detail = _FakeDetail()
        self.view_box = _FakeView()

    def add_annotation(self, *args, **kwargs) -> None:
        pass


class _Rect:
    def __init__(self, image: np.ndarray, key=("http://f", 1)) -> None:
        self._image = image
        self.frame_key = key
        self.is_image = True
        self.scale_x = self.scale_y = 1.0
        self.localization_index = 0
        self.source_url = key[0]
        self.association = SimpleNamespace(uuid="u")

    def get_image(self, should_cancel=None) -> np.ndarray:
        return self._image

    def set_source_image_dimensions(self, *_args) -> None:
        pass


def _setup(adjustment: DisplayAdjustment):
    frame = np.full((40, 60, 3), (30, 90, 60), np.uint8)
    rect = _Rect(frame)
    context = SimpleNamespace(adjustment=adjustment, corrector=ColourCorrector())
    box_handler = _DetailBoxHandler()
    remembered: list = []
    pool = _InlinePool()
    coordinator = DetailPaneCoordinator(
        box_handler_getter=lambda: box_handler,
        selected_rect_getter=lambda: rect,
        display_context_getter=lambda: context,
        frame_loaded_callback=lambda r, params: remembered.append(params),
        thread_pool_getter=lambda: pool,
    )
    return coordinator, rect, context, box_handler, remembered, pool


def test_frame_is_measured_and_converted_on_the_worker() -> None:
    coordinator, rect, context, box_handler, remembered, _pool = _setup(
        DisplayAdjustment(colour_correct=True)
    )
    coordinator.show_rect_in_detail_async(rect, needs_autorange=False)

    assert len(remembered) == 1 and remembered[0].shape == (7,)
    shown = box_handler.roi_detail.images[-1]
    assert shown.shape == (40, 60, 3) and shown.flags["C_CONTIGUOUS"]

    # Measured frames aren't measured again.
    context.corrector.store_frame(rect.frame_key, remembered[0])
    coordinator.show_rect_in_detail_async(rect, needs_autorange=False)
    assert len(remembered) == 1


def test_plain_frame_is_shown_as_rgb() -> None:
    coordinator, rect, _context, box_handler, _remembered, _pool = _setup(
        DisplayAdjustment()
    )
    coordinator.show_rect_in_detail_async(rect, needs_autorange=False)
    shown = box_handler.roi_detail.images[-1]
    assert tuple(shown[0, 0]) == (60, 90, 30)  # BGR (30, 90, 60) as RGB


def test_view_change_redraws_on_a_worker() -> None:
    coordinator, rect, context, box_handler, _remembered, pool = _setup(
        DisplayAdjustment()
    )
    coordinator.show_rect_in_detail_async(rect, needs_autorange=False)
    started = pool.started
    before = box_handler.roi_detail.images[-1]

    context.adjustment = DisplayAdjustment(brightness=50)
    coordinator.refresh_display()

    assert pool.started == started + 1
    after = box_handler.roi_detail.images[-1]
    assert after.mean() > before.mean()


def test_stale_view_redraw_is_dropped() -> None:
    coordinator, rect, _context, box_handler, _remembered, _pool = _setup(
        DisplayAdjustment()
    )
    coordinator.show_rect_in_detail_async(rect, needs_autorange=False)
    count = len(box_handler.roi_detail.images)
    raw = coordinator._raw_detail_image
    # A redraw result for an older request arrives late.
    coordinator._on_display_worker_result(
        (coordinator._display_generation - 1, raw, raw)
    )
    assert len(box_handler.roi_detail.images) == count


def test_settings_changed_while_loading_triggers_a_redraw() -> None:
    coordinator, rect, context, box_handler, _remembered, pool = _setup(
        DisplayAdjustment()
    )
    frame = rect.get_image()
    payload = DetailPaneCoordinator._load_detail_image_worker(
        rect,
        1,
        False,
        True,
        1.0,
        1.0,
        lambda: False,
        context.adjustment,
        context.corrector,
        rect.frame_key,
    )
    coordinator._detail_request_generation = 1
    context.adjustment = DisplayAdjustment(brightness=50)  # changed meanwhile
    coordinator._on_detail_worker_result(payload)

    assert pool.started == 1  # the redraw with the new settings
    assert box_handler.roi_detail.images[-1].mean() > frame.mean()
