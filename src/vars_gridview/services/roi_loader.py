"""ROI loader service for preparing mosaic ROI widget data.

`RoiLoader` encapsulates non-Qt ROI preparation logic used by `ImageMosaic`.
It computes per-group source context, fetches missing image references, and
returns plain data specs that the UI layer uses to construct `RectWidget`
instances on the main thread.

Thread-affinity note:
    ``RectWidget`` is a Qt graphics widget and must be created on the GUI
    thread. This loader returns plain data specs only and does not construct
    Qt widgets.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from iso8601 import parse_date

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.common.time import get_timestamp
from vars_gridview.lib.m3.clients import AnnosaurusClient, VampireSquidClient

if TYPE_CHECKING:
    from vars_gridview.lib.annotation.association import BoundingBoxAssociation


@dataclass
class RoiLoadResult:
    """Result bundle returned by `RoiLoader.create_widget_specs`."""

    widget_specs: list["RoiWidgetSpec"]
    n_images: int
    n_localizations: int
    failed_association_uuids: list[UUID]


@dataclass
class RoiWidgetSpec:
    """Plain data required to construct one mosaic `RectWidget`."""

    associations: list["BoundingBoxAssociation"]
    source_url: str
    is_image: bool
    ancillary_data: dict
    video_data: dict
    association_index: int
    scale_x: float
    scale_y: float
    video_url: str | None
    elapsed_time_millis: int | None


class RoiLoader:
    """Build plain ROI widget specs from grouped localization metadata."""

    def fetch_video_sequence_data(
        self,
        *,
        vampire_squid_client: VampireSquidClient,
        moment_video_data: dict[UUID, dict],
        video_sequences_by_name: dict[str, dict | None],
        progress_callback: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        """Fetch and cache video-sequence records needed by current moments."""
        video_sequence_names = set(
            video_data["video_sequence_name"]
            for video_data in moment_video_data.values()
            if video_data.get("video_sequence_name", None) is not None
        )
        video_sequence_names -= set(video_sequences_by_name.keys())

        total = len(video_sequence_names)
        if progress_callback is not None:
            progress_callback(0, total)

        with ThreadPoolExecutor(max_workers=10) as executor:
            vs_futures = {
                executor.submit(
                    vampire_squid_client.get_video_sequence_by_name, name
                ): name
                for name in video_sequence_names
            }

            done = 0
            for vs_future in as_completed(vs_futures):
                if should_cancel is not None and should_cancel():
                    for future in vs_futures:
                        future.cancel()
                    executor.shutdown(wait=False)
                    raise RuntimeError("Video sequence fetch cancelled")

                sequence_name = vs_futures[vs_future]
                try:
                    response = vs_future.result()
                    response.raise_for_status()
                    video_sequence_data = response.json()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(
                        f"Failed to get video sequence data for {sequence_name}: {exc}"
                    )
                    video_sequence_data = None

                if video_sequence_data is not None:
                    video_sequences_by_name[video_sequence_data["name"]] = (
                        video_sequence_data
                    )

                done += 1
                if progress_callback is not None:
                    progress_callback(done, total)

    def map_proxy_data(
        self,
        *,
        rows: list[object],
        moment_proxy_data: dict[UUID, dict | None],
        moment_timestamps: dict[UUID, object],
        video_sequences_by_name: dict[str, dict | None],
        progress_callback: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        """Populate per-moment proxy video mappings used for ROI creation."""
        total = len(rows)
        if progress_callback is not None:
            progress_callback(0, total)

        for idx, row in enumerate(rows, start=1):
            if should_cancel is not None and should_cancel():
                raise RuntimeError("Proxy mapping cancelled")

            imaged_moment_uuid = getattr(row, "imaged_moment_uuid")
            if imaged_moment_uuid in moment_proxy_data:
                if progress_callback is not None and (idx == total or idx % 250 == 0):
                    progress_callback(idx, total)
                continue

            moment_timestamp = get_timestamp(
                getattr(row, "video_start_timestamp"),
                getattr(row, "index_recorded_timestamp"),
                getattr(row, "index_elapsed_time_millis"),
                getattr(row, "index_timecode"),
            )
            moment_timestamps[imaged_moment_uuid] = moment_timestamp

            if moment_timestamp is None:
                continue

            mp4_video_data = self.find_mp4_video_data(
                video_sequence_name=getattr(row, "video_sequence_name"),
                timestamp=moment_timestamp,
                video_sequences_by_name=video_sequences_by_name,
            )

            if mp4_video_data is None:
                LOGGER.warning(
                    f"Could not find MP4 video reference for imaged moment {imaged_moment_uuid}"
                )

            moment_proxy_data[imaged_moment_uuid] = mp4_video_data

            if progress_callback is not None and (idx == total or idx % 250 == 0):
                progress_callback(idx, total)

    def find_mp4_video_data(
        self,
        *,
        video_sequence_name: str | None,
        timestamp: datetime,
        video_sequences_by_name: dict[str, dict | None],
    ) -> dict | None:
        """Return video + video-reference metadata for an MP4 covering timestamp."""
        if not video_sequence_name:
            return None
        if video_sequence_name not in video_sequences_by_name:
            return None

        video_sequence = video_sequences_by_name[video_sequence_name]
        if video_sequence is None:
            return None

        videos = video_sequence.get("videos", [])
        for video in videos:
            video_duration_millis = video.get("duration_millis", None)
            if video_duration_millis is None:
                continue

            video_start_timestamp = video.get("start_timestamp", None)
            if video_start_timestamp is None:
                continue

            video_start_timestamp = parse_date(video_start_timestamp)
            video_end_timestamp = video_start_timestamp + timedelta(
                milliseconds=video_duration_millis
            )

            if not (video_start_timestamp <= timestamp <= video_end_timestamp):
                continue

            video_references = video.get("video_references", [])
            for video_reference in video_references:
                container = video_reference.get("container", None)
                if container != "video/mp4":
                    continue

                return {
                    "video": video,
                    "video_reference": video_reference,
                }

        return None

    def create_widget_specs(
        self,
        *,
        annosaurus_client: AnnosaurusClient,
        association_groups: dict[tuple[UUID, UUID | None], list],
        moment_video_data: dict[UUID, dict],
        moment_proxy_data: dict[UUID, dict | None],
        moment_timestamps: dict[UUID, object],
        image_reference_urls: dict[UUID | None, str | None],
        moment_ancillary_data: dict[UUID, dict],
        progress_callback: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> RoiLoadResult:
        """Create all ROI widget specs for the current query result set."""
        n_images = 0
        n_localizations = 0
        widget_specs: list[RoiWidgetSpec] = []
        failed_association_uuids: list[UUID] = []
        total = sum(len(group) for group in association_groups.values())
        done = 0
        if progress_callback is not None:
            progress_callback(0, total)

        for group_key, associations in association_groups.items():
            group_context = self._build_group_context(
                annosaurus_client=annosaurus_client,
                group_key=group_key,
                moment_video_data=moment_video_data,
                moment_proxy_data=moment_proxy_data,
                moment_timestamps=moment_timestamps,
                image_reference_urls=image_reference_urls,
            )
            if group_context is None:
                continue

            n_images += 1

            imaged_moment_uuid = group_key[0]
            ancillary_data = moment_ancillary_data.get(imaged_moment_uuid, {}) or {}
            video_data = moment_video_data.get(imaged_moment_uuid, {}) or {}

            for association in associations:
                if should_cancel is not None and should_cancel():
                    raise RuntimeError("ROI creation cancelled")

                other_locs = list(associations)
                other_locs.remove(association)

                try:
                    widget_specs.append(
                        RoiWidgetSpec(
                            associations=other_locs + [association],
                            source_url=group_context["source_url"],
                            is_image=group_context["is_image"],
                            ancillary_data=ancillary_data,
                            video_data=video_data,
                            association_index=len(other_locs),
                            scale_x=group_context["scale_x"],
                            scale_y=group_context["scale_y"],
                            video_url=group_context["video_url"],
                            elapsed_time_millis=group_context["elapsed_time_millis"],
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(f"Error preparing rect widget spec: {exc}")
                    failed_association_uuids.append(association.uuid)
                n_localizations += 1
                done += 1
                if progress_callback is not None:
                    progress_callback(done, total)

        return RoiLoadResult(
            widget_specs=widget_specs,
            n_images=n_images,
            n_localizations=n_localizations,
            failed_association_uuids=failed_association_uuids,
        )

    def _build_group_context(
        self,
        *,
        annosaurus_client: AnnosaurusClient,
        group_key: tuple[UUID, UUID | None],
        moment_video_data: dict[UUID, dict],
        moment_proxy_data: dict[UUID, dict | None],
        moment_timestamps: dict[UUID, object],
        image_reference_urls: dict[UUID | None, str | None],
    ) -> dict | None:
        """Compute source/proxy details for one association group."""
        imaged_moment_uuid, image_reference_uuid = group_key

        scale_x = 1.0
        scale_y = 1.0
        source_url = None
        video_url = None
        elapsed_time_millis = None

        video_data = moment_video_data[imaged_moment_uuid]
        moment_timestamp = moment_timestamps[imaged_moment_uuid]
        if not isinstance(moment_timestamp, datetime):
            LOGGER.error(
                f"Imaged moment {imaged_moment_uuid} has no valid timestamp, skipping"
            )
            return None

        original_video_reference_uri = video_data.get("video_uri", None)
        use_proxy = (
            original_video_reference_uri is None
            or not original_video_reference_uri.startswith("http")
        )

        if use_proxy:
            proxy_video_data = moment_proxy_data.get(imaged_moment_uuid, None)
            if proxy_video_data is None:
                LOGGER.error(
                    f"Imaged moment {imaged_moment_uuid} has no proxy video reference, skipping"
                )
                return None

            source_width = video_data.get("video_width", None)
            source_height = video_data.get("video_height", None)
            proxy_video_reference = proxy_video_data.get("video_reference", {})
            proxy_width = proxy_video_reference.get("width", None)
            proxy_height = proxy_video_reference.get("height", None)
            if (
                proxy_width is None
                or proxy_height is None
                or source_width is None
                or source_height is None
            ):
                LOGGER.error(
                    f"Imaged moment {imaged_moment_uuid} is missing video dimensions needed for proxy scaling, skipping"
                )
                return None
            scale_x = source_width / proxy_width
            scale_y = source_height / proxy_height

            proxy_video = proxy_video_data.get("video", {})
            proxy_video_start_timestamp = proxy_video.get("start_timestamp", None)
            if proxy_video_start_timestamp is None:
                LOGGER.error(
                    f"Imaged moment {imaged_moment_uuid} proxy video reference missing start timestamp, skipping"
                )
                return None
            proxy_video_start_timestamp = parse_date(proxy_video_start_timestamp)

            elapsed_time_millis = round(
                (moment_timestamp - proxy_video_start_timestamp).total_seconds() * 1000
            )
            video_url = proxy_video_data["video_reference"]["uri"]
        else:
            original_video_start_timestamp = video_data["video_start_timestamp"]
            elapsed_time_millis = round(
                (moment_timestamp - original_video_start_timestamp).total_seconds()
                * 1000
            )
            video_url = original_video_reference_uri

        is_image = image_reference_uuid is not None
        if not is_image:
            source_url = video_url
        else:
            url = image_reference_urls.get(image_reference_uuid, None)
            if url is None:
                try:
                    response = annosaurus_client.get_image_reference(
                        str(image_reference_uuid)
                    )
                    response.raise_for_status()
                    image_reference = response.json()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(
                        f"Error getting image reference {image_reference_uuid}: {exc}"
                    )
                    return None

                url = image_reference.get("url", None)
                if url is None:
                    LOGGER.error(
                        f"Image reference {image_reference_uuid} has no URL, skipping"
                    )
                    return None

            source_url = url

            if scale_x == 0.0:
                scale_x = 1.0
            if scale_y == 0.0:
                scale_y = 1.0

        return {
            "source_url": source_url,
            "is_image": is_image,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "video_url": video_url,
            "elapsed_time_millis": elapsed_time_millis,
        }


__all__ = ["RoiLoader", "RoiLoadResult", "RoiWidgetSpec"]
