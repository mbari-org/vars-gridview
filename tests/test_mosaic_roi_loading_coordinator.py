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
    def __init__(self, *, fail_times: int = 0) -> None:
        self.roiRefreshed = _FakeSignal()
        self.roi_batch_generation = None
        # Number of upcoming request_roi_refresh() calls that should result
        # in roi_loaded=False before the tile "succeeds".
        self._fail_times = fail_times
        self.roi_loaded = False
        self.refresh_calls = 0

    def assign_roi_batch_generation(self, generation) -> None:
        self.roi_batch_generation = generation

    def request_roi_refresh(self, *, debounce: bool = True) -> None:
        self.refresh_calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            self.roi_loaded = False
        else:
            self.roi_loaded = True
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


def test_failed_tile_is_retried_by_sweep_and_recovers() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    coordinator._schedule_retry = lambda delay, callback: callback()

    widgets = [_FakeRectWidget(), _FakeRectWidget(fail_times=1)]
    on_complete_calls = []

    coordinator.start_loading(
        rect_widgets=widgets,
        on_complete=lambda: on_complete_calls.append(True),
        cancel_event=Event(),
    )

    assert widgets[1].roi_loaded is True
    # One failing attempt in the initial pass, one successful sweep retry.
    assert widgets[1].refresh_calls == 2
    assert widgets[0].refresh_calls == 1
    # on_complete fires once for the initial pass and once more once the
    # sweep repairs the failed tile.
    assert on_complete_calls == [True, True]


def test_sweep_gives_up_after_configured_attempts() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    coordinator._schedule_retry = lambda delay, callback: callback()

    widgets = [_FakeRectWidget(fail_times=1000)]  # never recovers
    on_complete_calls = []

    coordinator.start_loading(
        rect_widgets=widgets,
        on_complete=lambda: on_complete_calls.append(True),
        cancel_event=Event(),
    )

    assert widgets[0].roi_loaded is False
    expected_attempts = 1 + len(mrc._SWEEP_RETRY_DELAYS_SECONDS)
    assert widgets[0].refresh_calls == expected_attempts
    assert on_complete_calls == [True] * expected_attempts


def test_no_sweep_scheduled_when_nothing_failed() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    scheduled = []
    coordinator._schedule_retry = lambda delay, callback: scheduled.append(callback)

    widgets = [_FakeRectWidget() for _ in range(3)]
    coordinator.start_loading(
        rect_widgets=widgets, on_complete=lambda: None, cancel_event=Event()
    )

    assert scheduled == []


def test_sweep_pass_does_not_emit_progress() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    coordinator._schedule_retry = lambda delay, callback: callback()
    progress_calls = []
    coordinator.progress.connect(
        lambda current, total: progress_calls.append((current, total))
    )

    widgets = [_FakeRectWidget(fail_times=1)]
    coordinator.start_loading(
        rect_widgets=widgets, on_complete=lambda: None, cancel_event=Event()
    )

    # Only the initial pass emits progress; the sweep pass runs silently.
    assert progress_calls == [(0, 1), (1, 1)]


def test_cancel_mid_load_stops_pumping_and_skips_callback() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=1)
    cancel_event = Event()
    widgets = [_FakeRectWidget() for _ in range(3)]

    original_request = widgets[0].request_roi_refresh

    def cancelling_request(*, debounce: bool = True) -> None:
        cancel_event.set()
        original_request(debounce=debounce)

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
