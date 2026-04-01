from __future__ import annotations

from types import SimpleNamespace

import pytest

from vars_gridview.ui.mosaic.image_mosaic import Cancelled, ImageMosaic


class _FakeCoordinator:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def run_stage(self, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._result


def _fake_image_mosaic(result=None, error: Exception | None = None):
    return SimpleNamespace(
        _load_coordinator=_FakeCoordinator(result=result, error=error)
    )


def test_run_cancellable_stage_maps_cancel_runtime_error() -> None:
    fake_self = _fake_image_mosaic(error=RuntimeError("cancelled"))

    with pytest.raises(Cancelled):
        ImageMosaic._run_cancellable_stage(
            fake_self,
            label="stage",
            maximum=1,
            cancelled_message="cancelled",
            missing_result_message=None,
            worker_factory=lambda _cancel_event, _progress: None,
        )


def test_run_cancellable_stage_propagates_other_runtime_error() -> None:
    fake_self = _fake_image_mosaic(error=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        ImageMosaic._run_cancellable_stage(
            fake_self,
            label="stage",
            maximum=1,
            cancelled_message="cancelled",
            missing_result_message=None,
            worker_factory=lambda _cancel_event, _progress: None,
        )


def test_run_cancellable_stage_enforces_missing_result_message() -> None:
    fake_self = _fake_image_mosaic(result=None)

    with pytest.raises(RuntimeError, match="missing"):
        ImageMosaic._run_cancellable_stage(
            fake_self,
            label="stage",
            maximum=1,
            cancelled_message="cancelled",
            missing_result_message="missing",
            worker_factory=lambda _cancel_event, _progress: None,
        )


def test_run_cancellable_stage_returns_result() -> None:
    fake_self = _fake_image_mosaic(result={"ok": True})

    result = ImageMosaic._run_cancellable_stage(
        fake_self,
        label="stage",
        maximum=1,
        cancelled_message="cancelled",
        missing_result_message="missing",
        worker_factory=lambda _cancel_event, _progress: None,
    )

    assert result == {"ok": True}
