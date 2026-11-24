"""Read embeddings already stored in the VARS vector database.

MBARI keeps an embedding of every VARS bounding box in a Qdrant collection
(``vars_annotations``): one point per association, whose id is the
association UUID, with a named vector per model -- ``dinov3``,
``bioclip2-image``, ``siglip2-image`` -- the same names as the embedding
service's ``/embed/image/{model}`` routes. Fetching those is far faster than
computing them (about 5,000 vectors in under a second, against minutes of
embedding, which also needs every tile image downloaded first), and works
while the embedding service is down.

Measured against the embedding service on the same crops (2026-11-23):
cosine 1.0000 for still-image crops and 0.98-0.999 for video-frame crops
(frame-decoding differences), so stored and freshly computed vectors can be
mixed in one similarity ranking.

A stored vector is only used when the box it was computed on (``box`` in the
point's payload) still matches the localization: a box resized since then
gets a fresh embedding instead.

Talks to Qdrant's REST API with ``requests``, so it adds no dependency.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

import numpy as np
import requests

from vars_gridview.lib.runtime.log import LOGGER

FETCH_BATCH = 1000
BOX_TOLERANCE_PX = 1.0
TIMEOUT = (5, 60)


@dataclass(frozen=True)
class BoxQuery:
    """One localization to look up: its association UUID and current box."""

    association_uuid: UUID
    x: float
    y: float
    width: float
    height: float


class VarsVectorStore:
    """Fetch stored embeddings by association UUID from the VARS Qdrant."""

    def __init__(self, base_url: str, collection: str) -> None:
        self._base_url = base_url.strip().rstrip("/")
        self._collection = collection.strip()
        self._session = requests.Session()
        self._vector_names: set[str] | None = None
        self._lock = threading.Lock()

    @property
    def description(self) -> str:
        return f"{self._base_url} ({self._collection})"

    def vector_names(self) -> set[str]:
        """Named vectors the collection holds (cached after the first call)."""
        with self._lock:
            if self._vector_names is None:
                response = self._session.get(
                    f"{self._base_url}/collections/{self._collection}", timeout=TIMEOUT
                )
                response.raise_for_status()
                vectors = response.json()["result"]["config"]["params"]["vectors"]
                self._vector_names = set(vectors) if isinstance(vectors, dict) else {""}
            return set(self._vector_names)

    def fetch(
        self, boxes: Iterable[BoxQuery], vector_name: str
    ) -> tuple[dict[UUID, np.ndarray], int]:
        """Stored *vector_name* vectors for *boxes*.

        Returns ``(vectors by association UUID, stale)``: only points whose
        stored box matches the current one are returned; *stale* counts the
        points skipped because the box changed since. Associations with no
        point (not yet indexed) are simply absent.
        """
        names = self.vector_names()
        if vector_name not in names:
            raise ValueError(
                f"The VARS vector database has no '{vector_name}' vectors "
                f"(it has: {', '.join(sorted(names))})."
            )
        wanted = {str(b.association_uuid).lower(): b for b in boxes}
        ids = list(wanted)
        vectors: dict[UUID, np.ndarray] = {}
        stale = 0
        for start in range(0, len(ids), FETCH_BATCH):
            response = self._session.post(
                f"{self._base_url}/collections/{self._collection}/points",
                json={
                    "ids": ids[start : start + FETCH_BATCH],
                    "with_vector": [vector_name],
                    "with_payload": ["box.x", "box.y", "box.width", "box.height"],
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            for point in response.json().get("result", []):
                query = wanted.get(str(point.get("id", "")).lower())
                vector = (point.get("vector") or {}).get(vector_name)
                if query is None or not vector:
                    continue
                if not self._same_box(query, (point.get("payload") or {}).get("box")):
                    stale += 1
                    continue
                vectors[query.association_uuid] = np.asarray(vector, dtype=np.float32)
        return vectors, stale

    @staticmethod
    def _same_box(query: BoxQuery, stored: object) -> bool:
        if not isinstance(stored, dict):
            return True  # nothing to compare against: trust the id
        try:
            return all(
                abs(float(stored[key]) - float(value)) <= BOX_TOLERANCE_PX
                for key, value in (
                    ("x", query.x),
                    ("y", query.y),
                    ("width", query.width),
                    ("height", query.height),
                )
            )
        except (KeyError, TypeError, ValueError):
            LOGGER.debug(f"Unreadable stored box for {query.association_uuid}")
            return True


__all__ = ["BoxQuery", "VarsVectorStore"]
