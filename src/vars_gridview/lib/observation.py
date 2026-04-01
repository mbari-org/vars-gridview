"""Domain model for a VARS observation."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class Observation(BaseModel):
    """A single VARS observation.

    An observation records *what* was seen (``concept``), *by whom*
    (``observer``), and links back to the imaged moment it belongs to.

    Attributes:
        uuid: Unique identifier of this observation in Annosaurus.
        concept: Scientific or common name of the observed organism/object.
        observer: Username of the observer who created this annotation.
        group: Observation group tag (e.g. ``"deep-sea"`` or ``"ROV"``).
        imaged_moment_uuid: UUID of the parent imaged moment.
    """

    uuid: UUID
    concept: str
    observer: str
    group: str
    imaged_moment_uuid: UUID


__all__ = ["Observation"]
