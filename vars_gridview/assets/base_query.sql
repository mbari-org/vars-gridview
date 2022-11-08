SELECT DISTINCT
    imaged_moment_uuid,
    image_reference_uuid,
    anno.observation_uuid AS observation_uuid,
    video_reference_uuid,
    anno.index_elapsed_time_millis,
    anno.index_recorded_timestamp,
    anno.index_timecode,
    anno.video_start_timestamp,
    anno.video_uri,
    anno.video_container,
    assoc.uuid AS association_uuid,
    image_url, image_format,
    observer, concept,
    assoc.link_name AS link_name,
    assoc.to_concept AS to_concept,
    assoc.link_value AS link_value,
    chief_scientist,
    dive_number,
    camera_platform,
    depth_meters,
    latitude,
    longitude,
    oxygen_ml_per_l,
    pressure_dbar,
    salinity,
    temperature_celsius,
    light_transmission
FROM
    annotations anno INNER JOIN associations assoc ON anno.observation_uuid = assoc.observation_uuid
WHERE
    {filters}