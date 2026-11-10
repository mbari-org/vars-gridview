"""Coordinator for asynchronous ROI tile loading lifecycle in the mosaic."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import TYPE_CHECKING, cast

from PyQt6 import QtCore

from vars_gridview.lib.runtime.log import LOGGER

if TYPE_CHECKING:
    from vars_gridview.lib.net import BackpressureThrottle
    from vars_gridview.ui.mosaic.rect_widget import RectWidget

# Tiles that still fail after the initial pass (e.g. caught in a cold-cache
# backpressure storm) get a few more automatic chances once things have had
# a chance to quiet down, at reduced concurrency so the sweep itself doesn't
# reproduce the overload that caused the failures. These run silently (no
# `progress` signal) since they're a background repair, not something the
# user needs a progress bar for -- affected tiles still visibly flip from
# placeholder to loaded as they succeed. The delay between sweeps grows the
# same way the throttle's own per-request retry delay does, rather than being
# a separate hardcoded schedule.
_SWEEP_BASE_DELAY_SECONDS = 3.0
_SWEEP_MAX_DELAY_SECONDS = 30.0
_SWEEP_MAX_ATTEMPTS = 3
_SWEEP_MAX_CONCURRENCY = 4


class MosaicRoiLoadingCoordinator(QtCore.QObject):
    """Own ROI loading queueing and completion callback.

    Does not own any UI presentation itself; callers connect to
    :attr:`progress` to drive their own shared progress display.
    """

    progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        max_concurrency: int = 4,
    ) -> None:
        super().__init__(parent)
        self._max_concurrency = max(1, int(max_concurrency))
        self._current_max_concurrency = self._max_concurrency

        self._generation = 0
        self._total = 0
        self._done = 0
        self._pending: list[RectWidget] = []
        self._inflight = 0
        self._failed: list[RectWidget] = []
        self._is_sweep_pass = False
        self._sweep_attempt = 0
        self._pass_finished = True
        self._top_level_on_complete: Callable[[], None] | None = None
        self._cancel_event: Event | None = None
        self._throttle: BackpressureThrottle | None = None

    def set_throttle(self, throttle: BackpressureThrottle | None) -> None:
        """Share a backpressure signal used to scale down dispatch concurrency.

        When set, :meth:`_pump` reads the throttle's current concurrency
        scale on every dispatch cycle, so a burst of 503s from any tile fetch
        (not just ones this coordinator dispatched) slows new dispatches down,
        and recovery ramps concurrency back up gradually.
        """
        self._throttle = throttle

    def cancel_pending(self) -> None:
        """Invalidate in-flight ROI refreshes."""
        self._generation += 1
        self._total = 0
        self._done = 0
        self._pending = []
        self._inflight = 0
        self._failed = []
        self._is_sweep_pass = False
        self._sweep_attempt = 0
        self._pass_finished = True
        self._top_level_on_complete = None
        self._cancel_event = None

    def start_loading(
        self,
        *,
        rect_widgets: list[RectWidget],
        on_complete: Callable[[], None],
        cancel_event: Event,
    ) -> None:
        """Start batched async ROI loading for the given widgets."""
        if not rect_widgets:
            return

        self.cancel_pending()
        self._top_level_on_complete = on_complete
        self._cancel_event = cancel_event
        self._begin_pass(rect_widgets)

    def _begin_pass(
        self,
        rect_widgets: list[RectWidget],
        *,
        max_concurrency: int | None = None,
        is_sweep: bool = False,
    ) -> None:
        self._generation += 1
        generation = self._generation

        self._current_max_concurrency = max(1, max_concurrency or self._max_concurrency)
        self._is_sweep_pass = is_sweep
        self._total = len(rect_widgets)
        self._done = 0
        self._pending = list(rect_widgets)
        self._inflight = 0
        self._failed = []
        self._pass_finished = False

        if not is_sweep:
            self.progress.emit(self._done, self._total)
        self._pump(generation)

    def _effective_max_concurrency(self) -> int:
        if self._throttle is None:
            return self._current_max_concurrency
        scale = self._throttle.concurrency_scale()
        scaled = round(self._current_max_concurrency * scale)
        return max(1, min(self._current_max_concurrency, scaled))

    def _pump(self, generation: int) -> None:
        while (
            generation == self._generation
            and self._inflight < self._effective_max_concurrency()
            and self._pending
            and not (self._cancel_event is not None and self._cancel_event.is_set())
        ):
            rect_widget = self._pending.pop(0)
            rect_widget.assign_roi_batch_generation(generation)
            rect_widget.roiRefreshed.connect(self._on_rect_roi_refreshed)
            self._inflight += 1
            # No debounce: the coordinator calls this exactly once per tile,
            # so there's nothing to coalesce -- unlike interactive callers
            # (e.g. dragging a box), which legitimately fire repeatedly and
            # rely on the default debounce to coalesce them.
            rect_widget.request_roi_refresh(debounce=False)

    @QtCore.pyqtSlot(object)
    def _on_rect_roi_refreshed(self, rect_widget: object) -> None:
        rw = cast("RectWidget", rect_widget)
        try:
            rw.roiRefreshed.disconnect(self._on_rect_roi_refreshed)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(f"roiRefreshed already disconnected: {exc}")

        if rw.roi_batch_generation != self._generation:
            return

        self._inflight = max(0, self._inflight - 1)
        self._done += 1
        if not rw.roi_loaded:
            self._failed.append(rw)
        if not self._is_sweep_pass:
            self.progress.emit(self._done, self._total)

        self._pump(self._generation)

        cancelled = self._cancel_event is not None and self._cancel_event.is_set()
        if cancelled:
            if self._inflight == 0:
                self._top_level_on_complete = None
            return

        if self._done >= self._total:
            self._finish_pass()

    def _finish_pass(self) -> None:
        # _pump's recursion means every stack frame between the first tile's
        # completion and the last one re-checks `done >= total` once control
        # unwinds back to it -- guard so a pass only finishes once.
        if self._pass_finished:
            return
        self._pass_finished = True

        callback = self._top_level_on_complete
        failed = list(self._failed)
        generation = self._generation

        if callback is not None:
            callback()

        if (
            not failed
            or self._sweep_attempt >= _SWEEP_MAX_ATTEMPTS
            or (self._cancel_event is not None and self._cancel_event.is_set())
        ):
            return

        delay_seconds = min(
            _SWEEP_BASE_DELAY_SECONDS * (2**self._sweep_attempt),
            _SWEEP_MAX_DELAY_SECONDS,
        )
        self._sweep_attempt += 1
        LOGGER.info(
            f"{len(failed)} tile(s) failed to load; retrying in {delay_seconds:.0f}s "
            f"(sweep {self._sweep_attempt}/{_SWEEP_MAX_ATTEMPTS})"
        )

        def _retry() -> None:
            if generation != self._generation:
                return  # superseded by a new batch or explicit cancellation
            targets = [rw for rw in failed if not rw.roi_loaded]
            if not targets:
                return
            self._begin_pass(
                targets, max_concurrency=_SWEEP_MAX_CONCURRENCY, is_sweep=True
            )

        self._schedule_retry(delay_seconds, _retry)

    def _schedule_retry(
        self, delay_seconds: float, callback: Callable[[], None]
    ) -> None:
        """Run *callback* after *delay_seconds*. Overridable in tests to run inline."""
        QtCore.QTimer.singleShot(int(delay_seconds * 1000), callback)


__all__ = ["MosaicRoiLoadingCoordinator"]
