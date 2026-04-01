from __future__ import annotations

import requests

from vars_gridview.services.roi_service import RoiService


class _FakeAssoc:
    def __init__(self, uuid: str = "assoc-1") -> None:
        self.uuid = uuid
        self.box = (1, 1, 3, 3)


class _FakeResponse:
    def __init__(self, content: bytes = b"img") -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeSkimmer:
    def __init__(self, *, raise_http_error: bool = False) -> None:
        self.raise_http_error = raise_http_error
        self.calls = []

    def crop(self, image_url, x, y, xf, yf):
        self.calls.append((image_url, x, y, xf, yf))
        if self.raise_http_error:
            raise requests.HTTPError("crop failed")
        return _FakeResponse(b"skimmer")


class _FakeBeholder:
    def __init__(self, payload: bytes = b"frame") -> None:
        self.payload = payload
        self.calls = []

    def capture_raw(self, image_url, elapsed_time_millis):
        self.calls.append((image_url, elapsed_time_millis))
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
