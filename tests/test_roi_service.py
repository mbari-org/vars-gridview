from __future__ import annotations

import httpx
import requests

from vars_gridview.services.roi_service import RoiService


def _httpx_status_error(
    status_code: int, headers: dict | None = None
) -> httpx.HTTPStatusError:
    """Build a realistic httpx.HTTPStatusError, as beholder_client raises on non-2xx."""
    request = httpx.Request("POST", "https://beholder.example/capture")
    response = httpx.Response(status_code, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("busy", request=request, response=response)


class _FakeAssoc:
    def __init__(self, uuid: str = "assoc-1") -> None:
        self.uuid = uuid
        self.box = (1, 1, 3, 3)


class _FakeResponse:
    def __init__(
        self,
        content: bytes = b"img",
        status_code: int = 200,
        headers: dict | None = None,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class _FakeSkimmer:
    def __init__(
        self, *, raise_http_error: bool = False, responses: list | None = None
    ) -> None:
        self.raise_http_error = raise_http_error
        self.calls = []
        # If given, one queued response is returned per call (in order),
        # letting tests script a sequence like [503, 503, 200].
        self._responses = list(responses) if responses is not None else None

    def crop(self, image_url, x, y, xf, yf):
        self.calls.append((image_url, x, y, xf, yf))
        if self.raise_http_error:
            raise requests.HTTPError("crop failed")
        if self._responses is not None:
            return self._responses.pop(0)
        return _FakeResponse(b"skimmer")


class _FakeBeholder:
    def __init__(
        self, payload: bytes = b"frame", responses: list | None = None
    ) -> None:
        self.payload = payload
        self.calls = []
        # If given, one queued item is consumed per call, in order: bytes on
        # success, or an exception instance to raise (e.g. an
        # httpx.HTTPStatusError for a 503).
        self._responses = list(responses) if responses is not None else None

    def capture_raw(self, image_url, elapsed_time_millis):
        self.calls.append((image_url, elapsed_time_millis))
        if self._responses is not None:
            item = self._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return self.payload


class _FakeArray:
    def __init__(self) -> None:
        self.slices = []

    def __getitem__(self, item):
        self.slices.append(item)
        return "roi-slice"


def test_fetch_roi_uses_skimmer_for_static_images(monkeypatch) -> None:
    skimmer = _FakeSkimmer()
    service = RoiService(skimmer=skimmer, beholder=_FakeBeholder())

    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: "decoded",
    )

    result = service.fetch_roi(_FakeAssoc(), "https://example/image.jpg")

    assert skimmer.calls == [("https://example/image.jpg", 1, 1, 3, 3)]
    assert result == "decoded"


def test_fetch_roi_uses_beholder_for_video_frames(monkeypatch) -> None:
    beholder = _FakeBeholder()
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    fake_image = _FakeArray()
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: fake_image,
    )

    result = service.fetch_roi(
        _FakeAssoc(), "https://example/video.mp4", elapsed_time_millis=123
    )

    assert beholder.calls == [("https://example/video.mp4", 123)]
    assert result == "roi-slice"


def test_fetch_roi_returns_none_on_skimmer_http_error() -> None:
    service = RoiService(
        skimmer=_FakeSkimmer(raise_http_error=True), beholder=_FakeBeholder()
    )

    result = service.fetch_roi(_FakeAssoc(), "https://example/image.jpg")

    assert result is None


def test_fetch_full_image_uses_requests_for_static_images(monkeypatch) -> None:
    service = RoiService(skimmer=_FakeSkimmer(), beholder=_FakeBeholder())

    monkeypatch.setattr(
        "vars_gridview.services.roi_service.requests.get",
        lambda *_args, **_kwargs: _FakeResponse(b"img"),
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: "decoded-full",
    )

    result = service.fetch_full_image("https://example/image.jpg")

    assert result == "decoded-full"


def test_fetch_full_image_returns_none_on_unexpected_error(monkeypatch) -> None:
    service = RoiService(skimmer=_FakeSkimmer(), beholder=_FakeBeholder())

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("vars_gridview.services.roi_service.requests.get", _boom)

    assert service.fetch_full_image("https://example/image.jpg") is None


def test_fetch_roi_returns_none_when_beholder_decode_fails(monkeypatch) -> None:
    beholder = _FakeBeholder()
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: None,
    )

    result = service.fetch_roi(
        _FakeAssoc(),
        "https://example/video.mp4",
        elapsed_time_millis=200,
    )

    assert beholder.calls == [("https://example/video.mp4", 200)]
    assert result is None


def test_fetch_full_image_returns_none_when_decode_fails(monkeypatch) -> None:
    service = RoiService(skimmer=_FakeSkimmer(), beholder=_FakeBeholder())

    monkeypatch.setattr(
        "vars_gridview.services.roi_service.requests.get",
        lambda *_args, **_kwargs: _FakeResponse(b"img"),
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: None,
    )

    result = service.fetch_full_image("https://example/image.jpg")

    assert result is None


def test_fetch_roi_retries_skimmer_503_then_succeeds(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.time.sleep", lambda s: sleeps.append(s)
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: "decoded",
    )

    skimmer = _FakeSkimmer(
        responses=[
            _FakeResponse(status_code=503, headers={"Retry-After": "0.5"}),
            _FakeResponse(status_code=503, headers={"Retry-After": "0.5"}),
            _FakeResponse(b"skimmer", status_code=200),
        ]
    )
    service = RoiService(skimmer=skimmer, beholder=_FakeBeholder())

    result = service.fetch_roi(_FakeAssoc(), "https://example/image.jpg")

    assert result == "decoded"
    assert len(skimmer.calls) == 3
    assert sleeps == [0.5, 0.5]


def test_fetch_roi_gives_up_after_max_retries_on_persistent_503(monkeypatch) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    skimmer = _FakeSkimmer(
        responses=[_FakeResponse(status_code=503) for _ in range(10)]
    )
    service = RoiService(skimmer=skimmer, beholder=_FakeBeholder())

    result = service.fetch_roi(_FakeAssoc(), "https://example/image.jpg")

    assert result is None
    # Initial attempt plus the configured number of retries, no more.
    assert len(skimmer.calls) == 3


def test_fetch_roi_retry_after_header_is_capped(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.time.sleep", lambda s: sleeps.append(s)
    )
    skimmer = _FakeSkimmer(
        responses=[
            _FakeResponse(status_code=503, headers={"Retry-After": "9999"}),
            _FakeResponse(status_code=503, headers={"Retry-After": "not-a-number"}),
            _FakeResponse(status_code=503),
        ]
    )
    service = RoiService(skimmer=skimmer, beholder=_FakeBeholder())

    service.fetch_roi(_FakeAssoc(), "https://example/image.jpg")

    assert sleeps[0] == 5.0  # capped
    assert sleeps[1] == 1.0  # unparsable -> default


def test_fetch_roi_retries_beholder_503_then_succeeds(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.time.sleep", lambda s: sleeps.append(s)
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: _FakeArray(),
    )

    beholder = _FakeBeholder(
        responses=[
            _httpx_status_error(503, headers={"Retry-After": "0.5"}),
            _httpx_status_error(503, headers={"Retry-After": "0.5"}),
            b"frame",
        ]
    )
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    result = service.fetch_roi(
        _FakeAssoc(), "https://example/video.mp4", elapsed_time_millis=123
    )

    assert result == "roi-slice"
    assert len(beholder.calls) == 3
    assert sleeps == [0.5, 0.5]


def test_fetch_roi_gives_up_after_max_retries_on_persistent_beholder_503(
    monkeypatch,
) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    beholder = _FakeBeholder(responses=[_httpx_status_error(503) for _ in range(10)])
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    result = service.fetch_roi(
        _FakeAssoc(), "https://example/video.mp4", elapsed_time_millis=123
    )

    assert result is None
    # Initial attempt plus the configured number of retries, no more.
    assert len(beholder.calls) == 3


def test_fetch_roi_does_not_retry_non_503_beholder_errors(monkeypatch) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    beholder = _FakeBeholder(responses=[_httpx_status_error(500)])
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    result = service.fetch_roi(
        _FakeAssoc(), "https://example/video.mp4", elapsed_time_millis=123
    )

    assert result is None
    assert len(beholder.calls) == 1


def test_fetch_full_image_retries_beholder_503_past_the_bulk_retry_budget(
    monkeypatch,
) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: "decoded",
    )

    # More failures than fetch_roi's small retry budget would tolerate --
    # the interactive full-image path should keep going regardless.
    beholder = _FakeBeholder(
        responses=[_httpx_status_error(503) for _ in range(5)] + [b"frame"]
    )
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    result = service.fetch_full_image(
        "https://example/video.mp4", elapsed_time_millis=123
    )

    assert result == "decoded"
    assert len(beholder.calls) == 6


def test_fetch_full_image_stops_retrying_once_cancelled(monkeypatch) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    beholder = _FakeBeholder(responses=[_httpx_status_error(503) for _ in range(10)])
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    calls_before_cancel = 2
    seen = {"n": 0}

    def should_cancel() -> bool:
        seen["n"] += 1
        return seen["n"] >= calls_before_cancel

    result = service.fetch_full_image(
        "https://example/video.mp4",
        elapsed_time_millis=123,
        should_cancel=should_cancel,
    )

    assert result is None
    assert len(beholder.calls) == calls_before_cancel


def test_fetch_full_image_gives_up_once_deadline_passes(monkeypatch) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    # First call establishes the deadline; second (the post-failure check)
    # reports time already past it, so a single failure is not retried.
    times = iter([0.0, 1000.0])
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.time.monotonic", lambda: next(times)
    )
    beholder = _FakeBeholder(responses=[_httpx_status_error(503) for _ in range(10)])
    service = RoiService(skimmer=_FakeSkimmer(), beholder=beholder)

    result = service.fetch_full_image(
        "https://example/video.mp4", elapsed_time_millis=123
    )

    assert result is None
    assert len(beholder.calls) == 1


def test_fetch_full_image_retries_static_image_503(monkeypatch) -> None:
    monkeypatch.setattr("vars_gridview.services.roi_service.time.sleep", lambda s: None)
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.np.frombuffer",
        lambda *_args, **_kwargs: b"arr",
    )
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.cv2.imdecode",
        lambda *_args, **_kwargs: "decoded",
    )

    responses = [
        _FakeResponse(status_code=503),
        _FakeResponse(status_code=503),
        _FakeResponse(b"img", status_code=200),
    ]
    monkeypatch.setattr(
        "vars_gridview.services.roi_service.requests.get",
        lambda *_args, **_kwargs: responses.pop(0),
    )

    service = RoiService(skimmer=_FakeSkimmer(), beholder=_FakeBeholder())
    result = service.fetch_full_image("https://example/image.jpg")

    assert result == "decoded"
    assert responses == []
