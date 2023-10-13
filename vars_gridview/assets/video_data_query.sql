SELECT
	vs.uuid AS video_sequence_uuid,
	vs.name AS video_sequence_name,
	v.uuid AS video_uuid,
	v.name AS video_name,
	v.start_time AS video_start_time,
	v.duration_millis AS video_duration_millis,
	vr.uuid AS video_reference_uuid,
	vr.uri AS video_reference_uri,
	vr.width AS video_reference_width,
	vr.height AS video_reference_height,
	vr.container AS video_reference_container
FROM
	M3_VIDEO_ASSETS.dbo.video_sequences vs
INNER JOIN
	M3_VIDEO_ASSETS.dbo.videos v ON v.video_sequence_uuid = vs.uuid
INNER JOIN
	M3_VIDEO_ASSETS.dbo.video_references vr ON vr.video_uuid = v.uuid
WHERE
	vr.uuid IN {video_reference_uuids}