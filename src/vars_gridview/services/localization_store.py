"""Pure data store for localization query results.

`LocalizationStore` owns the non-Qt state needed to build the mosaic:
metadata maps, association groups, and proxy-related lookup tables.
"""

from __future__ import annotations

from json import loads
from uuid import UUID

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.annotation.observation import Observation


class LocalizationStore:
    """State container for parsed query rows and derived metadata."""

    def __init__(self) -> None:
        self.image_reference_urls: dict[UUID | None, str | None] = {}
        self.association_groups: dict[
            tuple[UUID, UUID | None], list[BoundingBoxAssociation]
        ] = {}
        self.observations: dict[UUID, Observation] = {}
        self.moment_video_data: dict[UUID, dict] = {}
        self.moment_proxy_data: dict[UUID, dict | None] = {}
        self.moment_timestamps: dict[UUID, object] = {}
        self.video_sequences_by_name: dict[str, dict | None] = {}
        self.moment_ancillary_data: dict[UUID, dict] = {}

    def reset_for_query(self) -> None:
        """Clear query-derived state before loading a new result set."""
        self.association_groups.clear()
        self.observations.clear()
        self.moment_video_data.clear()
        self.moment_proxy_data.clear()
        self.moment_timestamps.clear()
        self.moment_ancillary_data.clear()

    def map_metadata(self, rows: list[object]) -> None:
        """Populate lookup tables from parsed query rows."""
        for row in rows:
            image_reference_uuid = getattr(row, "image_reference_uuid")
            image_url = getattr(row, "image_url")
            observation_uuid = getattr(row, "observation_uuid")
            concept = getattr(row, "concept")
            observer = getattr(row, "observer")
            observation_group = getattr(row, "observation_group")
            imaged_moment_uuid = getattr(row, "imaged_moment_uuid")
            video_uri = getattr(row, "video_uri")

            if image_reference_uuid not in self.image_reference_urls:
                self.image_reference_urls[image_reference_uuid] = image_url

            if observation_uuid not in self.observations:
                try:
                    observation = Observation(
                        uuid=observation_uuid,
                        concept=concept,
                        observer=observer,
                        group=observation_group,
                        imaged_moment_uuid=imaged_moment_uuid,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(
                        f"Error creating observation {observation_uuid} due to missing/invalid field: {exc}"
                    )
                    continue
                self.observations[observation_uuid] = observation

            if imaged_moment_uuid not in self.moment_ancillary_data:
                ancillary = {
                    "camera_platform": getattr(row, "camera_platform"),
                    "video_sequence_name": getattr(row, "video_sequence_name"),
                    "depth_meters": getattr(row, "depth_meters"),
                    "latitude": getattr(row, "latitude"),
                    "longitude": getattr(row, "longitude"),
                    "oxygen_ml_per_l": getattr(row, "oxygen_ml_per_l"),
                    "pressure_dbar": getattr(row, "pressure_dbar"),
                    "salinity": getattr(row, "salinity"),
                    "temperature_celsius": getattr(row, "temperature_celsius"),
                    "light_transmission": getattr(row, "light_transmission"),
                }
                self.moment_ancillary_data[imaged_moment_uuid] = {
                    k: v for k, v in ancillary.items() if v is not None
                }

            if (
                video_uri is not None
                and imaged_moment_uuid not in self.moment_video_data
            ):
                video_data = {
                    "index_elapsed_time_millis": getattr(
                        row, "index_elapsed_time_millis"
                    ),
                    "index_timecode": getattr(row, "index_timecode"),
                    "index_recorded_timestamp": getattr(
                        row, "index_recorded_timestamp"
                    ),
                    "video_start_timestamp": getattr(row, "video_start_timestamp"),
                    "video_uri": video_uri,
                    "video_container": getattr(row, "video_container"),
                    "video_reference_uuid": getattr(row, "video_reference_uuid"),
                    "video_sequence_name": getattr(row, "video_sequence_name"),
                    "video_width": getattr(row, "video_width"),
                    "video_height": getattr(row, "video_height"),
                }
                self.moment_video_data[imaged_moment_uuid] = {
                    k: v for k, v in video_data.items() if v is not None
                }

    def extract_associations(self, rows: list[object]) -> None:
        """Build association groups keyed by `(imaged_moment_uuid, image_reference_uuid)`."""
        seen_associations: set[UUID] = set()
        for row in rows:
            if getattr(row, "link_name") != "bounding box":
                continue

            association_uuid = getattr(row, "association_uuid")
            if association_uuid in seen_associations:
                continue
            seen_associations.add(association_uuid)

            imaged_moment_uuid = getattr(row, "imaged_moment_uuid")
            video_start_timestamp = getattr(row, "video_start_timestamp")
            video_sequence_name = getattr(row, "video_sequence_name")
            observation_uuid = getattr(row, "observation_uuid")
            to_concept = getattr(row, "to_concept")
            link_value = getattr(row, "link_value")

            if video_start_timestamp is None:
                LOGGER.warning(
                    f"Imaged moment {imaged_moment_uuid} has no video start timestamp, skipping"
                )
                continue

            if video_sequence_name is None:
                LOGGER.warning(
                    f"Imaged moment {imaged_moment_uuid} has no video sequence name, skipping"
                )
                continue

            observation = self.observations.get(observation_uuid)
            if observation is None:
                LOGGER.warning(
                    f"Association {association_uuid} has invalid observation {observation_uuid}, skipping"
                )
                continue

            try:
                box_data = loads(link_value)
                association = BoundingBoxAssociation(
                    association_uuid,
                    box_data,
                    observation,
                    to_concept,
                )
            except (KeyError, ValueError) as exc:
                LOGGER.error(
                    f"Invalid bounding box for association {association_uuid}: {exc}"
                )
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(
                    f"Unexpected error while creating bounding box association {association_uuid}: {exc}",
                    exc_info=True,
                )
                continue

            group_key = (imaged_moment_uuid, association.image_reference_uuid)
            if group_key not in self.association_groups:
                self.association_groups[group_key] = []
            self.association_groups[group_key].append(association)


__all__ = ["LocalizationStore"]
