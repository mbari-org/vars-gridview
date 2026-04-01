"""Localization loader service.

This module provides :class:`LocalizationLoader`, which executes an Annosaurus
TSV query and parses the result rows into
:class:`~vars_gridview.lib.association.BoundingBoxAssociation` objects grouped
by imaged-moment UUID.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.m3.clients import AnnosaurusClient
from vars_gridview.lib.m3.query import QueryRequest
from vars_gridview.lib.observation import Observation
from vars_gridview.lib.utils import parse_tsv

_log = logging.getLogger(__name__)

# Columns requested from Annosaurus.
QUERY_COLUMNS = [
    "observation_uuid",
    "concept",
    "observer",
    "group",
    "imaged_moment_uuid",
    "image_reference_uuid",
    "url",
    "video_start_timestamp",
    "recorded_timestamp",
    "elapsed_time_millis",
    "timecode",
    "association_uuid",
    "link_name",
    "link_value",
    "to_concept",
    "video_sequence_name",
    "ancillary_data",
]

BOUNDING_BOX_LINK_NAME = "bounding box"


class LocalizationGroup:
    """A collection of localizations (bounding boxes) from one imaged moment.

    Attributes:
        imaged_moment_uuid: UUID of the parent imaged moment.
        image_url: URL of the source frame image (may be ``None`` for video-only moments).
        elapsed_time_millis: Frame offset in ms (``None`` for still images).
        recorded_timestamp: ISO-8601 recorded timestamp string, or ``None``.
        video_start_timestamp: ISO-8601 video-start timestamp string, or ``None``.
        video_sequence_name: Name of the video sequence, or ``None``.
        ancillary_data: Free-form ancillary data dict (depth, salinity, etc.).
        associations: List of :class:`BoundingBoxAssociation` for this moment.
    """

    def __init__(self, imaged_moment_uuid: UUID) -> None:
        self.imaged_moment_uuid = imaged_moment_uuid
        self.image_url: str | None = None
        self.elapsed_time_millis: int | None = None
        self.recorded_timestamp: str | None = None
        self.video_start_timestamp: str | None = None
        self.video_sequence_name: str | None = None
        self.ancillary_data: dict = {}
        self.associations: list[BoundingBoxAssociation] = []


class LocalizationLoader:
    """Parse Annosaurus TSV query results into structured localizations.

    Args:
        client: Authenticated :class:`~vars_gridview.lib.m3.clients.AnnosaurusClient`.
        page_size: Number of rows to fetch per Annosaurus request.
    """

    def __init__(self, client: AnnosaurusClient, page_size: int = 5000) -> None:
        self._client = client
        self._page_size = page_size

    def load(self, query_request: QueryRequest) -> dict[UUID, LocalizationGroup]:
        """Execute *query_request* and return a map of imaged-moment UUID → group.

        Args:
            query_request: Query to execute against Annosaurus.  The ``select``
                field is overridden with :data:`QUERY_COLUMNS`.

        Returns:
            Ordered dict mapping each imaged-moment UUID to its
            :class:`LocalizationGroup` (order matches first-seen row order).

        Raises:
            requests.HTTPError: If any Annosaurus page request fails.
        """
        # Force the required column selection.
        request = QueryRequest(**query_request.to_dict())
        request.select = QUERY_COLUMNS
        request.limit = self._page_size
        request.offset = 0

        groups: dict[UUID, LocalizationGroup] = {}
        header: list[str] | None = None

        while True:
            response = self._client.query(request)
            response.raise_for_status()

            h, rows = parse_tsv(response.text)
            if header is None:
                header = h

            col = {name: idx for idx, name in enumerate(header)}

            for row in rows:
                if len(row) < len(header):
                    continue
                self._process_row(row, col, groups)

            request.offset += self._page_size  # type: ignore[operator]
            if len(rows) < self._page_size:
                break

        _log.debug(
            f"Loaded {sum(len(g.associations) for g in groups.values())} "
            f"localizations across {len(groups)} imaged moments"
        )
        return groups

    # ── Private helpers ────────────────────────────────────────────────────────

    def _process_row(
        self,
        row: list[str],
        col: dict[str, int],
        groups: dict[UUID, LocalizationGroup],
    ) -> None:
        def get(name: str) -> str:
            idx = col.get(name)
            return row[idx] if idx is not None and idx < len(row) else ""

        link_name = get("link_name")
        if link_name != BOUNDING_BOX_LINK_NAME:
            return

        link_value_raw = get("link_value")
        try:
            box_data: dict = json.loads(link_value_raw)
        except (json.JSONDecodeError, ValueError):
            _log.debug(f"Skipping row with invalid link_value: {link_value_raw!r}")
            return

        try:
            BoundingBoxAssociation.validate_data(box_data)
        except (KeyError, ValueError) as exc:
            _log.debug(f"Skipping invalid bounding box: {exc}")
            return

        im_uuid = UUID(get("imaged_moment_uuid"))
        if im_uuid not in groups:
            groups[im_uuid] = LocalizationGroup(im_uuid)

        group = groups[im_uuid]

        # Populate group-level fields from the first row seen for this moment.
        if group.image_url is None:
            group.image_url = get("url") or None
            etm = get("elapsed_time_millis")
            group.elapsed_time_millis = int(etm) if etm else None
            group.recorded_timestamp = get("recorded_timestamp") or None
            group.video_start_timestamp = get("video_start_timestamp") or None
            group.video_sequence_name = get("video_sequence_name") or None
            anc_raw = get("ancillary_data")
            if anc_raw:
                try:
                    group.ancillary_data = json.loads(anc_raw)
                except (json.JSONDecodeError, ValueError):
                    pass

        observation = Observation(
            uuid=UUID(get("observation_uuid")),
            concept=get("concept"),
            observer=get("observer"),
            group=get("group"),
            imaged_moment_uuid=im_uuid,
        )

        ir_raw = get("image_reference_uuid")
        if ir_raw:
            box_data["image_reference_uuid"] = ir_raw

        assoc = BoundingBoxAssociation(
            uuid=UUID(get("association_uuid")),
            data=box_data,
            observation=observation,
            to_concept=get("to_concept") or "self",
        )
        group.associations.append(assoc)


__all__ = ["LocalizationGroup", "LocalizationLoader", "QUERY_COLUMNS"]
