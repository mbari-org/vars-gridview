SELECT
	im.uuid AS imaged_moment_uuid,
	im.elapsed_time_millis AS imaged_moment_elapsed_time_millis,
	im.recorded_timestamp AS imaged_moment_recorded_timestamp,
	im.timecode AS imaged_moment_timecode,
	im.video_reference_uuid AS imaged_moment_video_reference_uuid,
	o.uuid AS observation_uuid,
	o.concept AS observation_concept,
	o.observer AS observation_observer,
	a.link_name AS association_link_name,
	a.to_concept AS association_to_concept,
	a.link_value AS association_link_value,
	ir.uuid AS image_reference_uuid,
	ir.format AS image_reference_format,
	ir.width_pixels AS image_reference_width_pixels,
	ir.height_pixels AS image_reference_height_pixels,
	ir.url AS image_reference_url
FROM
	M3_ANNOTATIONS.dbo.imaged_moments im
INNER JOIN
	M3_ANNOTATIONS.dbo.observations o ON o.imaged_moment_uuid = im.uuid
INNER JOIN
	M3_ANNOTATIONS.dbo.associations a ON a.observation_uuid = o.uuid
INNER JOIN
	M3_ANNOTATIONS.dbo.ancillary_data ad ON ad.imaged_moment_uuid = im.uuid
INNER JOIN
	M3_ANNOTATIONS.dbo.image_references ir ON ir.imaged_moment_uuid = im.uuid
WHERE
	a.link_name = 'bounding box' AND
	a.link_value LIKE '{{%}}' AND
	ir.format = 'image/png' AND
    {filters}