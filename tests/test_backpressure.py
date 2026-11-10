from __future__ import annotations

from vars_gridview.lib.net.backpressure import BackpressureThrottle


def test_fresh_throttle_uses_base_delay_and_full_scale() -> None:
    throttle = BackpressureThrottle()

    assert throttle.next_delay_seconds(None) == 1.0
    assert throttle.concurrency_scale() == 1.0


def test_retry_after_wins_over_exponential_fallback() -> None:
    throttle = BackpressureThrottle()
    for _ in range(5):
        throttle.record_busy()

    assert throttle.next_delay_seconds(2.5) == 2.5


def test_delay_grows_exponentially_with_consecutive_busy_signals() -> None:
    throttle = BackpressureThrottle(base_delay_seconds=1.0, max_delay_seconds=30.0)

    delays = []
    for _ in range(6):
        throttle.record_busy()
        delays.append(throttle.next_delay_seconds(None))

    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]  # last one capped


def test_delay_capped_at_max_exponent_beyond_max_delay_reach() -> None:
    throttle = BackpressureThrottle(
        base_delay_seconds=1.0, max_delay_seconds=1000.0, max_exponent=3
    )

    for _ in range(10):
        throttle.record_busy()

    # Exponent capped at max_exponent=3 regardless of how many busy signals.
    assert throttle.next_delay_seconds(None) == 8.0


def test_success_decays_delay_one_step_at_a_time() -> None:
    throttle = BackpressureThrottle()
    for _ in range(3):
        throttle.record_busy()
    assert throttle.next_delay_seconds(None) == 4.0

    throttle.record_success()
    assert throttle.next_delay_seconds(None) == 2.0

    throttle.record_success()
    throttle.record_success()
    assert throttle.next_delay_seconds(None) == 1.0


def test_success_does_not_underflow_below_base_delay() -> None:
    throttle = BackpressureThrottle()
    throttle.record_success()
    throttle.record_success()

    assert throttle.next_delay_seconds(None) == 1.0


def test_concurrency_scale_halves_on_busy_and_floors() -> None:
    throttle = BackpressureThrottle(scale_floor=0.25)

    throttle.record_busy()
    assert throttle.concurrency_scale() == 0.5

    throttle.record_busy()
    assert throttle.concurrency_scale() == 0.25

    throttle.record_busy()  # floor holds
    assert throttle.concurrency_scale() == 0.25


def test_concurrency_scale_recovers_additively_on_success() -> None:
    throttle = BackpressureThrottle(scale_floor=0.25, scale_step=0.25)
    throttle.record_busy()
    throttle.record_busy()
    assert throttle.concurrency_scale() == 0.25

    throttle.record_success()
    assert throttle.concurrency_scale() == 0.5

    throttle.record_success()
    assert throttle.concurrency_scale() == 0.75

    throttle.record_success()
    assert throttle.concurrency_scale() == 1.0

    throttle.record_success()  # ceiling holds
    assert throttle.concurrency_scale() == 1.0
