from vars_gridview.ui.mosaic.image_mosaic import Row


def test_row_parse_representative_tsv_data():
    headers = [
        "video_reference_uuid",
        "imaged_moment_uuid",
        "observation_uuid",
        "association_uuid",
        "image_reference_uuid",
        "video_sequence_name",
        "chief_scientist",
        "camera_platform",
        "dive_number",
        "video_start_timestamp",
        "video_container",
        "video_uri",
        "video_width",
        "video_height",
        "index_elapsed_time_millis",
        "index_recorded_timestamp",
        "index_timecode",
        "image_url",
        "image_format",
        "observer",
        "concept",
        "link_name",
        "to_concept",
        "link_value",
        "depth_meters",
        "latitude",
        "longitude",
        "oxygen_ml_per_l",
        "pressure_dbar",
        "salinity",
        "temperature_celsius",
        "light_transmission",
        "observation_group",
    ]
    row = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
        "",  # empty -> None
        "seq-a",
        "null",  # null -> None
        "Ventana",
        "2916",
        "2024-01-02T03:04:05Z",
        "video/mp4",
        "https://example/video.mp4",
        "1920",
        "1080",
        "1234",
        "2024-01-02T03:04:06Z",
        "00:00:01:00",
        "https://example/image.jpg",
        "image/jpeg",
        "observer-a",
        "Some concept",
        "bounding box",
        "self",
        '{"x":1,"y":2,"width":3,"height":4}',
        "1000.1",
        "36.7",
        "-122.0",
        "2.1",
        "100.5",
        "34.2",
        "7.8",
        "0.4",
        "group-a",
    ]

    parsed = Row.parse(headers, row)

    assert str(parsed.video_reference_uuid) == "11111111-1111-1111-1111-111111111111"
    assert parsed.image_reference_uuid is None
    assert parsed.chief_scientist is None
    assert parsed.video_width == 1920
    assert parsed.video_height == 1080
    assert parsed.index_elapsed_time_millis == 1234
    assert parsed.video_start_timestamp is not None
    assert parsed.index_recorded_timestamp is not None
    assert parsed.link_name == "bounding box"
    assert parsed.depth_meters == 1000.1
