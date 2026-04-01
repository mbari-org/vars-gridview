"""ROI loader service for building mosaic rect widgets.

`RoiLoader` encapsulates the ROI widget construction pipeline used by
`ImageMosaic`. It computes per-group source context, fetches missing image
references, and creates `RectWidget` instances.

Thread-affinity note:
    ``RectWidget`` is a Qt graphics widget and must be created on the GUI
    thread. This loader therefore creates widgets synchronously while using
    thread pools only for non-Qt network/data tasks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pyqtgraph as pg
from iso8601 import parse_date

from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.utils import get_timestamp
from vars_gridview.ui.RectWidget import RectWidget

if TYPE_CHECKING:
    from vars_gridview.lib.embedding import Embedding


@dataclass
class RoiLoadResult:
    """Result bundle returned by `RoiLoader.create_rect_widgets`."""

    rect_widgets: list[RectWidget]
    n_images: int
    n_localizations: int
    failed_association_uuids: list[UUID]


class RoiLoader:
    """Build `RectWidget` instances from grouped localization metadata."""

    def fetch_video_sequence_data(
        self,
        *,
        moment_video_data: dict[UUID, dict],
        video_sequences_by_name: dict[str, dict | None],
    ) -> None:
        """Fetch and cache video-sequence records needed by current moments."""
        video_sequence_names = set(
            video_data["video_sequence_name"]
            for video_data in moment_video_data.values()
            if video_data.get("video_sequence_name", None) is not None
        )
        video_sequence_names -= set(video_sequences_by_name.keys())

        with (
            pg.ProgressDialog(
                "Fetching video sequence data...", maximum=len(video_sequence_names)
            ) as progress,
            ThreadPoolExecutor(max_workers=10) as executor,
        ):
            vs_futures = {
                executor.submit(operations.get_video_sequence_by_name, name): name
                for name in video_sequence_names
            }

            for vs_future in as_completed(vs_futures):
                if progress.wasCanceled():
                    for future in vs_futures:
                        future.cancel()
                    executor.shutdown(wait=False)
                    raise RuntimeError("Video sequence fetch cancelled")

                sequence_name = vs_futures[vs_future]
                try:
                    video_sequence_data = vs_future.result()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(
                        f"Failed to get video sequence data for {sequence_name}: {exc}"
                    )
                    video_sequence_data = None

                if video_sequence_data is not None:
                    video_sequences_by_name[video_sequence_data["name"]] = (
                        video_sequence_data
                    )

                progress += 1

    def map_proxy_data(
        self,
        *,
        rows: list[object],
        moment_proxy_data: dict[UUID, dict | None],
        moment_timestamps: dict[UUID, object],
        video_sequences_by_name: dict[str, dict | None],
    ) -> None:
        """Populate per-moment proxy video mappings used for ROI creation."""
        for row in rows:
            imaged_moment_uuid = getattr(row, "imaged_moment_uuid")
            if imaged_moment_uuid in moment_proxy_data:
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

    def create_rect_widgets(
        self,
        *,
        association_groups: dict[tuple[UUID, UUID | None], list],
        moment_video_data: dict[UUID, dict],
        moment_proxy_data: dict[UUID, dict | None],
        moment_timestamps: dict[UUID, object],
        image_reference_urls: dict[UUID | None, str | None],
        moment_ancillary_data: dict[UUID, dict],
        rect_clicked_slot,
        similarity_sort_slot,
        rect_label_slot,
        rect_verify_slot,
        rect_mark_training_slot,
        embedding_model: Embedding | None,
    ) -> RoiLoadResult:
        """Create all ROI widgets for the current query result set.

        The method preserves existing behavior from `ImageMosaic._create_rois`:
        progress reporting, per-association error handling, and proxy scaling
        logic.
        """
        n_images = 0
        n_localizations = 0
        rect_widgets: list[RectWidget] = []
        failed_association_uuids: list[UUID] = []

        with (
            pg.ProgressDialog(
                "Creating ROIs...",
                0,
                sum(len(group) for group in association_groups.values()),
            ) as dlg,
        ):
            for group_key, associations in association_groups.items():
                group_context = self._build_group_context(
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
                    if dlg.wasCanceled():
                        raise RuntimeError("ROI creation cancelled")

                    other_locs = list(associations)
                    other_locs.remove(association)

                    try:
                        rw = RectWidget(
                            other_locs + [association],
                            group_context["source_url"],
                            group_context["is_image"],
                            ancillary_data,
                            video_data,
                            len(other_locs),
                            rect_clicked_slot,
                            similarity_sort_slot,
                            rect_label_slot,
                            rect_verify_slot,
                            rect_mark_training_slot,
                            text_label=association.text_label,
                            embedding_model=embedding_model,
                            scale_x=group_context["scale_x"],
                            scale_y=group_context["scale_y"],
                            video_url=group_context["video_url"],
                            elapsed_time_millis=group_context["elapsed_time_millis"],
                            preload_roi=False,
                        )
                        rect_widgets.append(rw)
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.error(f"Error creating rect widget: {exc}")
                        failed_association_uuids.append(association.uuid)
                    n_localizations += 1
                    dlg += 1

        return RoiLoadResult(
            rect_widgets=rect_widgets,
            n_images=n_images,
            n_localizations=n_localizations,
            failed_association_uuids=failed_association_uuids,
        )

    def _build_group_context(
        self,
        *,
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
                    image_reference = operations.get_image_reference(
                        str(image_reference_uuid)
                    )
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


__all__ = ["RoiLoader", "RoiLoadResult"]
