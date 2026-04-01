"""Service helpers for mosaic loading pipeline data preparation.

This module contains non-Qt worker payload builders used by ImageMosaic.
"""

from __future__ import annotations

from threading import Event
from typing import Callable
from uuid import UUID

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.services.localization_store import LocalizationStore
from vars_gridview.services.roi_loader import RoiLoader


class MosaicPipeline:
    """Build non-Qt data payloads for staged mosaic loading."""

    def build_localization_state(
        self,
        *,
        query_rows: list[list[str]],
        row_parser: Callable[[list[str]], object],
        cached_image_reference_urls: dict[UUID | None, str | None],
        cached_video_sequences_by_name: dict[str, dict | None],
        cancel_event: Event,
        progress_callback: Callable[[int, int], None],
        cancelled_message: str,
    ) -> tuple[list[object], LocalizationStore]:
        """Parse query rows and produce a fresh LocalizationStore snapshot."""
        rows: list[object] = []
        total = len(query_rows)
        if total == 0:
            store = LocalizationStore()
            store.image_reference_urls = cached_image_reference_urls
            store.video_sequences_by_name = cached_video_sequences_by_name
            return rows, store

        for idx, row in enumerate(query_rows, start=1):
            if cancel_event.is_set():
                raise RuntimeError(cancelled_message)

            try:
                rows.append(row_parser(row))
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(f"Error parsing row {row}: {exc}")

            if idx == total or idx % 250 == 0:
                progress_callback(idx, total)

        store = LocalizationStore()
        store.image_reference_urls = cached_image_reference_urls
        store.video_sequences_by_name = cached_video_sequences_by_name
        store.reset_for_query()
        store.map_metadata(rows)
        store.extract_associations(rows)
        return rows, store

    def build_proxy_mapping(
        self,
        *,
        rows: list[object],
        existing_moment_proxy_data: dict[UUID, dict | None],
        existing_moment_timestamps: dict[UUID, object],
        video_sequences_by_name: dict[str, dict | None],
        roi_loader: RoiLoader,
        cancel_event: Event,
        progress_callback: Callable[[int, int], None],
    ) -> tuple[dict[UUID, dict | None], dict[UUID, object]]:
        """Derive proxy mapping payload from parsed rows."""
        proxy_data = dict(existing_moment_proxy_data)
        timestamps = dict(existing_moment_timestamps)
        roi_loader.map_proxy_data(
            rows=list(rows),
            moment_proxy_data=proxy_data,
            moment_timestamps=timestamps,
            video_sequences_by_name=video_sequences_by_name,
            progress_callback=progress_callback,
            should_cancel=cancel_event.is_set,
        )
        return proxy_data, timestamps


__all__ = ["MosaicPipeline"]
