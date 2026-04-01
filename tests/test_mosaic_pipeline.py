from __future__ import annotations

from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest

from vars_gridview.services.mosaic_pipeline import MosaicPipeline


def test_build_localization_state_builds_store_and_rows() -> None:
    pipeline = MosaicPipeline()

    cached_urls = {
        UUID("11111111-1111-1111-1111-111111111111"): "https://example/a.jpg"
    }
    cached_sequences = {"seq-a": {"id": 1}}

    def _parser(row):
        return SimpleNamespace(
            imaged_moment_uuid=UUID("22222222-2222-2222-2222-222222222222"),
            observation_uuid=UUID("33333333-3333-3333-3333-333333333333"),
            association_uuid=UUID("44444444-4444-4444-4444-444444444444"),
            image_reference_uuid=UUID("11111111-1111-1111-1111-111111111111"),
            link_name="bounding box",
            link_value='{"x":1,"y":2,"width":3,"height":4}',
            video_sequence_name="seq-a",
            video_start_timestamp=datetime.now(timezone.utc),
            index_recorded_timestamp=None,
            index_elapsed_time_millis=1,
            index_timecode=None,
            video_uri="https://example/video.mp4",
            video_width=1920,
            video_height=1080,
            video_reference_uuid=UUID("55555555-5555-5555-5555-555555555555"),
            dive_number="1",
            camera_platform="platform",
            chief_scientist=None,
            video_container="video/mp4",
            observer="obs",
            concept="concept",
            observation_group="group",
            to_concept="self",
            depth_meters=None,
            latitude=None,
            longitude=None,
            oxygen_ml_per_l=None,
            pressure_dbar=None,
            salinity=None,
            temperature_celsius=None,
            light_transmission=None,
            image_url="https://example/a.jpg",
            image_format="image/jpeg",
        )

    rows, store = pipeline.build_localization_state(
        query_rows=[["one"]],
        row_parser=_parser,
        cached_image_reference_urls=cached_urls,
        cached_video_sequences_by_name=cached_sequences,
        cancel_event=Event(),
        progress_callback=lambda _current, _total: None,
        cancelled_message="cancelled",
    )

    assert len(rows) == 1
    assert store.image_reference_urls == cached_urls
    assert store.video_sequences_by_name == cached_sequences
    assert len(store.association_groups) == 1


def test_build_localization_state_cancelled() -> None:
    pipeline = MosaicPipeline()
    cancel_event = Event()
    cancel_event.set()

    with pytest.raises(RuntimeError, match="cancelled"):
        pipeline.build_localization_state(
            query_rows=[["one"]],
            row_parser=lambda _row: object(),
            cached_image_reference_urls={},
            cached_video_sequences_by_name={},
            cancel_event=cancel_event,
            progress_callback=lambda _current, _total: None,
            cancelled_message="cancelled",
        )


def test_build_proxy_mapping_delegates_to_roi_loader() -> None:
    pipeline = MosaicPipeline()

    seen = {}

    class _FakeRoiLoader:
        def map_proxy_data(self, **kwargs):
            seen.update(kwargs)
            kwargs["moment_proxy_data"][
                UUID("11111111-1111-1111-1111-111111111111")
            ] = {"video_reference": {"uri": "https://example/proxy.mp4"}}

    proxy_data, timestamps = pipeline.build_proxy_mapping(
        rows=[
            SimpleNamespace(
                imaged_moment_uuid=UUID("11111111-1111-1111-1111-111111111111")
            )
        ],
        existing_moment_proxy_data={},
        existing_moment_timestamps={},
        video_sequences_by_name={},
        roi_loader=_FakeRoiLoader(),
        cancel_event=Event(),
        progress_callback=lambda _current, _total: None,
    )

    assert "rows" in seen
    assert UUID("11111111-1111-1111-1111-111111111111") in proxy_data
    assert isinstance(timestamps, dict)
