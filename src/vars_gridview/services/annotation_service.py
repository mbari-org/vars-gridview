"""Annotation mutation service.

:class:`AnnotationService` is the **only** class that sends mutation requests
(create / update / delete) to Annosaurus.  All callers — controllers, UI slots
— must go through this service rather than calling ``lib.m3.operations``
functions directly.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.m3.clients import AnnosaurusClient

_log = logging.getLogger(__name__)


class AnnotationService:
    """Encapsulates all Annosaurus mutation operations.

    Args:
        client: Authenticated :class:`~vars_gridview.lib.m3.clients.AnnosaurusClient`.
        default_observer: Username appended to observation updates when the
            caller does not supply one explicitly.
    """

    def __init__(self, client: AnnosaurusClient, default_observer: str) -> None:
        self._client = client
        self._observer = default_observer

    # ── Observer ───────────────────────────────────────────────────────────────

    @property
    def observer(self) -> str:
        """Current default observer username."""
        return self._observer

    @observer.setter
    def observer(self, value: str) -> None:
        self._observer = value

    # ── Association mutations ──────────────────────────────────────────────────

    def push_changes(
        self,
        assoc: BoundingBoxAssociation,
        observer: str | None = None,
    ) -> None:
        """Flush all dirty state on *assoc* to Annosaurus.

        Checks the three dirty flags on *assoc* and issues only the HTTP calls
        that are actually needed.  Clears flags on success.

        Args:
            assoc: The association to persist.
            observer: Override for the observer username; falls back to
                :attr:`observer`.

        Raises:
            requests.HTTPError: On any Annosaurus error.
        """
        if assoc.deleted:
            return

        obs = observer or self._observer
        do_modify_box = False

        if assoc._dirty_concept:  # noqa: SLF001
            self._update_observation_concept(assoc.observation.uuid, assoc.concept, obs)
            assoc._dirty_concept = False  # noqa: SLF001
            do_modify_box = True

        if assoc._dirty_part:  # noqa: SLF001
            self._update_association_part(assoc.uuid, assoc.part)
            assoc._dirty_part = False  # noqa: SLF001
            do_modify_box = True

        if assoc._dirty_box:  # noqa: SLF001
            assoc._dirty_box = False  # noqa: SLF001
            do_modify_box = True

        if do_modify_box:
            self._update_bounding_box_data(assoc.uuid, assoc.data)

    def delete_association(self, assoc: BoundingBoxAssociation) -> None:
        """Delete *assoc* from Annosaurus and mark it locally as deleted.

        Args:
            assoc: Association to remove.

        Raises:
            requests.HTTPError: On network failure.
        """
        response = self._client.delete_association(str(assoc.uuid))
        response.raise_for_status()
        assoc.deleted = True
        _log.debug(f"Deleted association {assoc.uuid}")

    def delete_observation(self, observation_uuid: UUID) -> None:
        """Delete an entire observation (and all its associations) by UUID.

        Args:
            observation_uuid: UUID of the observation to remove.

        Raises:
            requests.HTTPError: On network failure.
        """
        response = self._client.delete_observation(str(observation_uuid))
        response.raise_for_status()
        _log.debug(f"Deleted observation {observation_uuid}")

    def get_observation_bounding_box_association_uuids(
        self, observation_uuid: UUID
    ) -> set[UUID]:
        """Return UUIDs of bounding-box associations for an observation.

        Args:
            observation_uuid: UUID of the observation to inspect.

        Returns:
            Set of association UUIDs whose ``link_name`` is ``"bounding box"``.

        Raises:
            requests.HTTPError: On network failure.
            ValueError: If an association UUID in the response is malformed.
        """
        response = self._client.get_observation(str(observation_uuid))
        response.raise_for_status()
        observation = response.json()

        uuids: set[UUID] = set()
        for association in observation.get("associations", []):
            if association.get("link_name") != "bounding box":
                continue
            uuids.add(UUID(str(association.get("uuid"))))
        return uuids

    # ── Private helpers ────────────────────────────────────────────────────────

    def _update_observation_concept(
        self, observation_uuid: UUID, concept: str, observer: str
    ) -> None:
        data = {"concept": concept, "observer": observer}
        response = self._client.update_observation(str(observation_uuid), data)
        response.raise_for_status()
        _log.debug(f"Updated concept for observation {observation_uuid} → {concept!r}")

    def _update_association_part(self, association_uuid: UUID, part: str) -> None:
        response = self._client.update_association(
            str(association_uuid), {"to_concept": part}
        )
        response.raise_for_status()
        _log.debug(f"Updated part for association {association_uuid} → {part!r}")

    def _update_bounding_box_data(self, association_uuid: UUID, box_data: dict) -> None:
        response = self._client.update_association(
            str(association_uuid), {"link_value": json.dumps(box_data)}
        )
        response.raise_for_status()
        _log.debug(f"Updated bounding box data for association {association_uuid}")


__all__ = ["AnnotationService"]
