"""M3 VARS API operations.

Thin wrappers around the HTTP clients in :mod:`vars_gridview.lib.m3`.  Each
function calls ``raise_for_status()`` and returns the parsed JSON or text body.

Module-level caches (``_cache``) avoid repeated round-trips for rarely-
changing catalogue data (concepts, parts, users, video-sequence names).  Call
:func:`clear_cache` to invalidate all caches at once, or assign ``None`` to
the relevant cache entry individually.

.. warning::
    These functions depend on the module-level client globals in
    :mod:`vars_gridview.lib.m3` (``ANNOSAURUS_CLIENT``, etc.).  They must not
    be called before :func:`~vars_gridview.lib.m3.setup_from_endpoint_data` has
    been executed.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable, Optional

import requests

from vars_gridview.lib import m3
from vars_gridview.lib.m3.query import QueryRequest
from vars_gridview.lib.utils import parse_tsv

_LOG = logging.getLogger(__name__)

# ── Module-level caches ──────────────────────────────────────────────────────
# Populated lazily on first use; each entry is ``None`` until fetched.

_kb_concepts: dict[str, str | None] | None = None  # concept → canonical name
_kb_parts: list[str] | None = None
_users: list[dict] | None = None
_video_sequence_names: list[str] | None = None

# Backward-compat aliases used by legacy code
KB_CONCEPTS = _kb_concepts
KB_PARTS = _kb_parts
USERS = _users
VIDEO_SEQUENCE_NAMES = _video_sequence_names


def clear_cache() -> None:
    """Invalidate all module-level caches.

    After this call the next access to :func:`get_kb_concepts`,
    :func:`get_kb_parts`, :func:`get_users`, or
    :func:`get_video_sequence_names` will re-fetch from the server.
    """
    global _kb_concepts, _kb_parts, _users, _video_sequence_names
    _kb_concepts = None
    _kb_parts = None
    _users = None
    _video_sequence_names = None


# ── Knowledge base ────────────────────────────────────────────────────────────


def get_kb_concepts() -> dict[str, str | None]:
    """Return all concepts in the knowledge base.

    The result is cached for the lifetime of the process (or until
    :func:`clear_cache` is called).

    Returns:
        Mapping of concept name → canonical name (``None`` until resolved via
        :func:`get_kb_name`).

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    global _kb_concepts
    if _kb_concepts is None:
        response = m3.VARS_KB_SERVER_CLIENT.get_concepts()
        response.raise_for_status()
        _kb_concepts = {name: None for name in response.json()}
        _LOG.debug("Fetched %d KB concepts", len(_kb_concepts))
    return _kb_concepts


def get_kb_name(concept: str) -> str:
    """Return the canonical name for *concept*.

    Resolves the name via the KB API on first call for a given concept (the
    result is stored in the :func:`get_kb_concepts` cache).

    Args:
        concept: A concept name as it appears in the annotation data.

    Returns:
        The canonical KB name (which may differ from *concept* due to aliasing).

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    kb_concepts = get_kb_concepts()
    if kb_concepts.get(concept) is None:
        response = m3.VARS_KB_SERVER_CLIENT.get_concept(concept)
        response.raise_for_status()
        name: str = response.json()["name"]
        kb_concepts[concept] = name
        _LOG.debug("Resolved KB name '%s' → '%s'", concept, name)
    return kb_concepts[concept]  # type: ignore[return-value]


def get_kb_parts() -> list[str]:
    """Return all body-part names defined in the knowledge base.

    The result is cached for the lifetime of the process.

    Returns:
        List of part name strings (e.g. ``["self", "anterior", …]``).

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    global _kb_parts
    if _kb_parts is None:
        response = m3.VARS_KB_SERVER_CLIENT.get_parts()
        response.raise_for_status()
        _kb_parts = [part["name"] for part in response.json()]
        _LOG.debug("Fetched %d KB parts", len(_kb_parts))
    return _kb_parts


def get_kb_descendants(concept: str) -> list[str]:
    """Return all phylogenetic descendants of *concept* (inclusive).

    Args:
        concept: Parent concept name.

    Returns:
        List of descendant names including *concept* itself.  Returns an empty
        list when the concept is not found in the KB.

    Raises:
        requests.exceptions.HTTPError: If the server request fails (except 404).
    """
    response = m3.VARS_KB_SERVER_CLIENT.get_phylogeny_taxa(concept)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    taxa: list[str] = [t["name"] for t in response.json()]
    _LOG.debug("Fetched %d descendants of '%s'", len(taxa), concept)
    return taxa


# ── Users ─────────────────────────────────────────────────────────────────────


def get_users() -> list[dict]:
    """Return all registered VARS users.

    Returns:
        List of user-data dicts as returned by the VARS user server.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    global _users
    if _users is None:
        response = m3.VARS_USER_SERVER_CLIENT.get_all_users()
        response.raise_for_status()
        _users = response.json()
        _LOG.debug("Fetched %d users", len(_users))
    return _users


# ── Annotation mutations ──────────────────────────────────────────────────────


def update_bounding_box_data(association_uuid: str, box_dict: dict) -> dict:
    """Update a bounding-box association's JSON payload (``link_value`` field).

    Args:
        association_uuid: UUID of the target association.
        box_dict: New bounding-box geometry/metadata dict.  It will be
            JSON-serialised and stored in the ``link_value`` column.

    Returns:
        Updated association dict as returned by Annosaurus.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.update_association(
        association_uuid, {"link_value": json.dumps(box_dict)}
    )
    response.raise_for_status()
    return response.json()


def update_bounding_box_part(association_uuid: str, part: str) -> dict:
    """Update a bounding-box association's body-part (``to_concept`` field).

    Args:
        association_uuid: UUID of the target association.
        part: New body-part name (e.g. ``"self"``, ``"anterior"``).

    Returns:
        Updated association dict as returned by Annosaurus.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.update_association(
        association_uuid, {"to_concept": part}
    )
    response.raise_for_status()
    return response.json()


def update_observation_concept(
    observation_uuid: str, concept: str, observer: str
) -> dict:
    """Update an observation's concept and observer fields.

    Args:
        observation_uuid: UUID of the target observation.
        concept: New concept name.
        observer: VARS user name of the person making the change.

    Returns:
        Updated observation dict as returned by Annosaurus.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.update_observation(
        observation_uuid, {"concept": concept, "observer": observer}
    )
    response.raise_for_status()
    return response.json()


def delete_association(association_uuid: str) -> None:
    """Permanently delete an association (bounding box) from VARS.

    Args:
        association_uuid: UUID of the association to delete.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.delete_association(association_uuid)
    response.raise_for_status()


def get_observation(observation_uuid: str) -> dict:
    """Fetch a single observation by UUID.

    Args:
        observation_uuid: UUID of the target observation.

    Returns:
        Observation dict as returned by Annosaurus.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.get_observation(observation_uuid)
    response.raise_for_status()
    return response.json()


def delete_observation(observation_uuid: str) -> None:
    """Permanently delete an observation (and all its associations) from VARS.

    Args:
        observation_uuid: UUID of the observation to delete.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.delete_observation(observation_uuid)
    response.raise_for_status()


# ── Video / image references ──────────────────────────────────────────────────


def get_video_sequence_by_name(name: str) -> dict:
    """Fetch a video sequence record by its deployment name.

    Args:
        name: Video sequence name (deployment identifier).

    Returns:
        Video-sequence dict as returned by VampireSquid.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.VAMPIRE_SQUID_CLIENT.get_video_sequence_by_name(name)
    response.raise_for_status()
    return response.json()


def get_image_reference(image_reference_uuid: str) -> dict:
    """Fetch an image reference record by UUID.

    Args:
        image_reference_uuid: UUID of the image reference.

    Returns:
        Image-reference dict as returned by Annosaurus.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    response = m3.ANNOSAURUS_CLIENT.get_image_reference(image_reference_uuid)
    response.raise_for_status()
    return response.json()


def get_video_sequence_names() -> list[str]:
    """Return the names of all video sequences known to VampireSquid.

    The result is cached for the lifetime of the process.

    Returns:
        List of video-sequence name strings.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    global _video_sequence_names
    if _video_sequence_names is None:
        response = m3.VAMPIRE_SQUID_CLIENT.get_video_sequence_names()
        response.raise_for_status()
        _video_sequence_names = response.json()
        _LOG.debug("Fetched %d video sequence names", len(_video_sequence_names))
    return _video_sequence_names


# ── Query ─────────────────────────────────────────────────────────────────────


def query(query_request: QueryRequest) -> str:
    """Execute a paged query against Annosaurus and return the TSV text.

    Args:
        query_request: Query parameters (constraints, limit, offset).

    Returns:
        TSV-formatted response body.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    _LOG.debug("Query: %s", query_request)
    response = m3.ANNOSAURUS_CLIENT.query(query_request)
    response.raise_for_status()
    return response.text


def query_paged(
    query_request: QueryRequest, page_size: int = 5000
) -> Iterable[list[str]]:
    """Execute a query in pages, yielding one row at a time.

    The first yielded value is the header row (list of column names).
    Subsequent values are data rows.

    Args:
        query_request: Base query parameters; ``limit`` and ``offset`` are
            overridden internally.
        page_size: Number of rows to fetch per request.

    Yields:
        Header row first, then one data row per iteration.

    Raises:
        requests.exceptions.HTTPError: If any page request fails.
    """
    request = QueryRequest(**query_request.to_dict())
    request.limit = page_size
    request.offset = 0

    headers_yielded = False
    while True:
        _LOG.debug("Query paged: offset=%d limit=%d", request.offset, request.limit)
        response_text = query(request)
        headers, rows = parse_tsv(response_text)

        if not headers_yielded:
            yield headers
            headers_yielded = True

        yield from rows

        request.offset += page_size
        if len(rows) < page_size:
            break


def query_download(query_request: QueryRequest) -> str:
    """Execute a query using the bulk-download endpoint and return TSV text.

    Args:
        query_request: Query parameters.

    Returns:
        TSV-formatted response body.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    _LOG.debug("Query download: %s", query_request)
    response = m3.ANNOSAURUS_CLIENT.query_download(query_request)
    response.raise_for_status()
    return response.text


def query_count(query_request: QueryRequest) -> int:
    """Return the total number of rows matching *query_request*.

    Args:
        query_request: Query parameters.

    Returns:
        Integer row count.

    Raises:
        requests.exceptions.HTTPError: If the server request fails.
    """
    _LOG.debug("Query count: %s", query_request)
    response = m3.ANNOSAURUS_CLIENT.query_count(query_request)
    response.raise_for_status()
    return response.json()["count"]


# ── Image cropping ────────────────────────────────────────────────────────────


def crop(
    url: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    ms: Optional[int] = None,
) -> requests.Response:
    """Crop a still image or video frame using the Skimmer service.

    Args:
        url: URL of the source image or video.
        left: Left boundary of the crop rectangle (pixels).
        top: Top boundary of the crop rectangle (pixels).
        right: Right boundary of the crop rectangle (pixels).
        bottom: Bottom boundary of the crop rectangle (pixels).
        ms: Millisecond timestamp for video sources; ``None`` for stills.

    Returns:
        Raw :class:`requests.Response` whose content is the cropped image bytes.

    Raises:
        requests.exceptions.HTTPError: If the Skimmer request fails.
    """
    response = m3.SKIMMER_CLIENT.crop(url, left, top, right, bottom, ms)
    response.raise_for_status()
    return response


__all__ = [
    "clear_cache",
    "get_kb_concepts",
    "get_kb_name",
    "get_kb_parts",
    "get_kb_descendants",
    "get_users",
    "update_bounding_box_data",
    "update_bounding_box_part",
    "update_observation_concept",
    "delete_association",
    "get_observation",
    "delete_observation",
    "get_video_sequence_by_name",
    "get_image_reference",
    "get_video_sequence_names",
    "query",
    "query_paged",
    "query_download",
    "query_count",
    "crop",
]
