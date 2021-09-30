SELECT DISTINCT
    imaged_moment_uuid,
    image_reference_uuid,
    anno.observation_uuid AS observation_uuid,
    video_reference_uuid,
    assoc.uuid AS association_uuid,
    image_url, image_format,
    observer, concept,
    assoc.link_name AS link_name,
    assoc.to_concept AS to_concept,
    assoc.link_value AS link_value,
    chief_scientist,
    dive_number,
    camera_platform
FROM
    annotations anno INNER JOIN associations assoc ON anno.observation_uuid = assoc.observation_uuid
WHERE
    image_reference_uuid IS NOT NULL AND
    image_url IS NOT NULL AND
    {filters}