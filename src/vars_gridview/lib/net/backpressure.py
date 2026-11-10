"""Shared backpressure signal for concurrent request throttling."""

from __future__ import annotations

import threading


class BackpressureThrottle:
    """Thread-safe shared backpressure signal for a pool of concurrent requests.

    Callers report each busy signal (e.g. an HTTP 503) via :meth:`record_busy`
    and each success via :meth:`record_success`, from as many threads as they
    like. A run of consecutive busy signals grows the exponential retry delay
    returned by :meth:`next_delay_seconds` and shrinks the concurrency scale
    returned by :meth:`concurrency_scale`; consecutive successes decay both
    back toward their resting state. This lets many independent callers (e.g.
    one worker thread per tile fetch) share one backpressure signal instead of
    each backing off in isolation.
    """

    def __init__(
        self,
        *,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
        max_exponent: int = 5,
        scale_floor: float = 0.25,
        scale_step: float = 0.25,
    ) -> None:
        self._base_delay = base_delay_seconds
        self._max_delay = max_delay_seconds
        self._max_exponent = max_exponent
        self._scale_floor = scale_floor
        self._scale_step = scale_step

        self._lock = threading.Lock()
        self._consecutive_busy = 0
        self._scale = 1.0

    def record_busy(self) -> None:
        """Report a busy signal (e.g. a 503), growing the backoff state."""
        with self._lock:
            self._consecutive_busy = min(
                self._consecutive_busy + 1, self._max_exponent + 1
            )
            self._scale = max(self._scale_floor, self._scale / 2.0)

    def record_success(self) -> None:
        """Report a success, decaying the backoff state one step."""
        with self._lock:
            self._consecutive_busy = max(0, self._consecutive_busy - 1)
            self._scale = min(1.0, self._scale + self._scale_step)

    def next_delay_seconds(self, retry_after: float | None) -> float:
        """Delay to wait before the next retry.

        Uses *retry_after* (already parsed/clamped by the caller) if given --
        the server telling us how long to wait beats guessing. Otherwise
        falls back to an exponential delay based on how many busy signals
        have been recorded in a row, capped at ``max_delay_seconds``.
        """
        if retry_after is not None:
            return retry_after
        with self._lock:
            exponent = max(0, self._consecutive_busy - 1)
        return min(self._base_delay * (2**exponent), self._max_delay)

    def concurrency_scale(self) -> float:
        """Current suggested concurrency scale, in ``(scale_floor, 1.0]``."""
        with self._lock:
            return self._scale


__all__ = ["BackpressureThrottle"]
