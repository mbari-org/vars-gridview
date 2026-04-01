from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from vars_gridview.services.roi_loader import RoiLoader


def test_map_proxy_data_populates_moment_proxy_and_timestamp() -> None:
    loader = RoiLoader()

    moment_uuid = UUID("11111111-1111-1111-1111-111111111111")
    row = SimpleNamespace(
        imaged_moment_uuid=moment_uuid,
        video_sequence_name="seq-a",
        video_start_timestamp=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        index_recorded_timestamp=None,
        index_elapsed_time_millis=5_000,
        index_timecode=None,
    )

    video_sequences_by_name = {
        "seq-a": {
            "videos": [
                {
                    "start_timestamp": "2024-01-01T00:00:00Z",
                    "duration_millis": 60_000,
                    "video_references": [
                        {
                            "container": "video/mp4",
                            "uri": "https://example/proxy.mp4",
                            "width": 960,
                            "height": 540,
                        }
                    ],
                }
            ]
        }
    }

    moment_proxy_data: dict[UUID, dict | None] = {}
    moment_timestamps: dict[UUID, object] = {}

    loader.map_proxy_data(
        rows=[row],
        moment_proxy_data=moment_proxy_data,
        moment_timestamps=moment_timestamps,
        video_sequences_by_name=video_sequences_by_name,
    )

    assert moment_uuid in moment_timestamps
    assert moment_uuid in moment_proxy_data
    assert moment_proxy_data[moment_uuid] is not None
    assert (
        moment_proxy_data[moment_uuid]["video_reference"]["uri"]
        == "https://example/proxy.mp4"
    )


def test_map_proxy_data_raises_on_cancellation() -> None:
    loader = RoiLoader()
    row = SimpleNamespace(
        imaged_moment_uuid=UUID("22222222-2222-2222-2222-222222222222"),
        video_sequence_name="seq-a",
        video_start_timestamp=datetime.now(timezone.utc),
        index_recorded_timestamp=None,
        index_elapsed_time_millis=0,
        index_timecode=None,
    )

    with pytest.raises(RuntimeError, match="Proxy mapping cancelled"):
        loader.map_proxy_data(
            rows=[row],
            moment_proxy_data={},
            moment_timestamps={},
            video_sequences_by_name={},
            should_cancel=lambda: True,
        )


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAnnosaurusClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_image_reference(self, image_reference_uuid: str) -> _FakeResponse:
        self.calls.append(image_reference_uuid)
        return _FakeResponse({"url": "https://example/fetched.jpg"})


def test_create_widget_specs_builds_expected_counts() -> None:
    loader = RoiLoader()
    annosaurus_client = _FakeAnnosaurusClient()

    moment_uuid = UUID("33333333-3333-3333-3333-333333333333")
    image_reference_uuid = UUID("44444444-4444-4444-4444-444444444444")
    assoc_a = SimpleNamespace(
        uuid=UUID("55555555-5555-5555-5555-555555555555"),
        text_label="A",
    )
    assoc_b = SimpleNamespace(
        uuid=UUID("66666666-6666-6666-6666-666666666666"),
        text_label="B",
    )

    now = datetime.now(timezone.utc)
    association_groups = {(moment_uuid, image_reference_uuid): [assoc_a, assoc_b]}
    moment_video_data = {
        moment_uuid: {
            "video_uri": "https://example/original.mp4",
            "video_start_timestamp": now - timedelta(seconds=10),
        }
    }
    moment_proxy_data = {moment_uuid: None}
    moment_timestamps = {moment_uuid: now}
    image_reference_urls = {image_reference_uuid: "https://example/image.jpg"}
    moment_ancillary_data = {moment_uuid: {"depth": 1000}}

    result = loader.create_widget_specs(
        annosaurus_client=annosaurus_client,
        association_groups=association_groups,
        moment_video_data=moment_video_data,
        moment_proxy_data=moment_proxy_data,
        moment_timestamps=moment_timestamps,
        image_reference_urls=image_reference_urls,
        moment_ancillary_data=moment_ancillary_data,
    )

    assert result.n_images == 1
    assert result.n_localizations == 2
    assert len(result.widget_specs) == 2
    assert result.failed_association_uuids == []
    assert annosaurus_client.calls == []

    for spec in result.widget_specs:
        assert spec.source_url == "https://example/image.jpg"
        assert spec.is_image is True
        assert spec.video_url == "https://example/original.mp4"
        assert spec.association_index == 1
        assert len(spec.associations) == 2
