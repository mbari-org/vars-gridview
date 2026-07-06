from __future__ import annotations

from threading import Event

from vars_gridview.ui.coordinators import mosaic_roi_loading_coordinator as mrc


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback) -> None:
        self._callbacks.remove(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class _FakeRectWidget:
    def __init__(self) -> None:
        self.roiRefreshed = _FakeSignal()
        self.roi_batch_generation = None

    def assign_roi_batch_generation(self, generation) -> None:
        self.roi_batch_generation = generation

    def request_roi_refresh(self) -> None:
        self.roiRefreshed.emit(self)


def test_start_loading_completes_and_calls_on_complete() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    widgets = [_FakeRectWidget() for _ in range(3)]
    progress_calls = []
    coordinator.progress.connect(
        lambda current, total: progress_calls.append((current, total))
    )
    on_complete_calls = []

    coordinator.start_loading(
        rect_widgets=widgets,
        on_complete=lambda: on_complete_calls.append(True),
        cancel_event=Event(),
    )

    assert on_complete_calls == [True]
    assert progress_calls[0] == (0, 3)
    assert progress_calls[-1] == (3, 3)


def test_cancel_mid_load_stops_pumping_and_skips_callback() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=1)
    cancel_event = Event()
    widgets = [_FakeRectWidget() for _ in range(3)]

    original_request = widgets[0].request_roi_refresh

    def cancelling_request() -> None:
        cancel_event.set()
        original_request()

    widgets[0].request_roi_refresh = cancelling_request
    on_complete_calls = []

    coordinator.start_loading(
        rect_widgets=widgets,
        on_complete=lambda: on_complete_calls.append(True),
        cancel_event=cancel_event,
    )

    assert on_complete_calls == []
    assert coordinator._done == 1
    assert widgets[1].roi_batch_generation is None
    assert widgets[2].roi_batch_generation is None
