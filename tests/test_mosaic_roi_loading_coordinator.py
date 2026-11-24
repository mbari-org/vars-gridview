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


class _SlowRectWidget(_FakeRectWidget):
    """Reports back only when :meth:`finish` is called (a fetch in flight)."""

    def request_roi_refresh(self, *, debounce: bool = True) -> None:
        self.refresh_calls += 1

    def finish(self, loaded: bool) -> None:
        self.roi_loaded = loaded
        self.roiRefreshed.emit(self)


def test_forget_failed_tile_is_not_retried_by_sweep() -> None:
    """Deleting a tile that failed to load must keep the sweep off it."""
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    scheduled = []
    coordinator._schedule_retry = lambda delay, callback: scheduled.append(callback)
    ok, bad = _FakeRectWidget(), _FakeRectWidget(fail_times=1000)
    coordinator.start_loading(
        rect_widgets=[ok, bad], on_complete=lambda: None, cancel_event=Event()
    )
    assert len(scheduled) == 1
    coordinator.forget([bad])
    scheduled[0]()
    assert bad.refresh_calls == 1  # never touched again


def test_forget_pending_and_inflight_tiles_still_finishes_pass() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=2)
    coordinator._schedule_retry = lambda delay, callback: None
    widgets = [_SlowRectWidget() for _ in range(4)]
    done = []
    coordinator.start_loading(
        rect_widgets=widgets,
        on_complete=lambda: done.append(True),
        cancel_event=Event(),
    )
    # 0 and 1 in flight, 2 and 3 queued. Delete one of each.
    coordinator.forget([widgets[1], widgets[3]])
    assert widgets[3].refresh_calls == 0
    widgets[0].finish(True)  # frees a slot: 2 starts
    assert widgets[2].refresh_calls == 1
    assert done == []
    widgets[2].finish(True)
    assert done == [True]
    # A late report from a forgotten tile changes nothing.
    widgets[1].finish(True)
    assert done == [True]
    assert coordinator._done == 2


def test_forget_last_inflight_tile_finishes_pass() -> None:
    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    coordinator._schedule_retry = lambda delay, callback: None
    a, b = _SlowRectWidget(), _SlowRectWidget()
    done = []
    coordinator.start_loading(
        rect_widgets=[a, b], on_complete=lambda: done.append(True), cancel_event=Event()
    )
    a.finish(True)
    coordinator.forget([b])
    assert done == [True]


def test_sweep_skips_qt_tile_deleted_without_forget() -> None:
    """The crash: a sweep retrying a tile whose C++ object Qt deleted."""
    from PyQt6 import QtCore, QtWidgets, sip

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class _QtTile(QtCore.QObject):
        roiRefreshed = QtCore.pyqtSignal(object)

        def __init__(self) -> None:
            super().__init__()
            self.roi_batch_generation = None
            self.roi_loaded = False
            self.refresh_calls = 0

        def assign_roi_batch_generation(self, generation) -> None:
            self.roi_batch_generation = generation

        def request_roi_refresh(self, *, debounce: bool = True) -> None:
            self.refresh_calls += 1
            self.roiRefreshed.emit(self)  # always fails

    coordinator = mrc.MosaicRoiLoadingCoordinator(parent=None, max_concurrency=4)
    scheduled = []
    coordinator._schedule_retry = lambda delay, callback: scheduled.append(callback)
    tiles = [_QtTile(), _QtTile()]
    done = []
    coordinator.start_loading(
        rect_widgets=tiles, on_complete=lambda: done.append(True), cancel_event=Event()
    )
    sip.delete(tiles[0])
    scheduled[0]()  # used to raise RuntimeError: ... has been deleted
    assert tiles[1].refresh_calls == 2
    assert done == [True, True]
