from uuid import UUID
from datetime import datetime, timezone

from vars_gridview.services.localization_store import LocalizationStore
from vars_gridview.ui.ImageMosaic import Row


def _make_row(association_uuid: str, link_name: str = "bounding box") -> Row:
    return Row(
        video_reference_uuid=UUID("11111111-1111-1111-1111-111111111111"),
        imaged_moment_uuid=UUID("22222222-2222-2222-2222-222222222222"),
        observation_uuid=UUID("33333333-3333-3333-3333-333333333333"),
        association_uuid=UUID(association_uuid),
        image_reference_uuid=None,
        video_sequence_name="seq-a",
        chief_scientist=None,
        camera_platform="Ventana",
        dive_number="2916",
        video_start_timestamp=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        video_container="video/mp4",
        video_uri="https://example/video.mp4",
        video_width=1920,
        video_height=1080,
        index_elapsed_time_millis=1234,
        index_recorded_timestamp=None,
        index_timecode="00:00:01:00",
        image_url="https://example/image.jpg",
        image_format="image/jpeg",
        observer="observer-a",
        concept="Some concept",
        observation_group="group-a",
        link_name=link_name,
        to_concept="self",
        link_value='{"x":1,"y":2,"width":3,"height":4}',
        depth_meters=1000.1,
        latitude=36.7,
        longitude=-122.0,
        oxygen_ml_per_l=2.1,
        pressure_dbar=100.5,
        salinity=34.2,
        temperature_celsius=7.8,
        light_transmission=0.4,
    )


def test_localization_store_maps_metadata_and_extracts_bounding_boxes():
    store = LocalizationStore()

    # One valid bounding-box association and one non-bounding association.
    rows = [
        _make_row("44444444-4444-4444-4444-444444444444", "bounding box"),
        _make_row("55555555-5555-5555-5555-555555555555", "comment"),
    ]

    store.map_metadata(rows)
    store.extract_associations(rows)

    assert len(store.observations) == 1
    assert len(store.moment_video_data) == 1
    assert len(store.moment_ancillary_data) == 1
    assert len(store.association_groups) == 1

    group = next(iter(store.association_groups.values()))
    assert len(group) == 1
    assert str(group[0].uuid) == "44444444-4444-4444-4444-444444444444"
