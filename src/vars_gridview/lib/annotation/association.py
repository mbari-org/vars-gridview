"""VARS bounding box association domain model.

This module contains :class:`BoundingBoxAssociation`, a pure data model that
represents a single bounding-box association record in Annosaurus.  It tracks
local mutations via dirty flags so the service layer knows what to persist.

Design note:
    This class intentionally contains **no** network I/O.  Use
    ``AnnotationService.push_changes()`` (in ``vars_gridview.services``) to
    flush dirty state back to Annosaurus.  The legacy :meth:`push_changes`
    method is retained for backward compatibility but delegates to the
    ``lib.m3.operations`` functions; new code should prefer the service layer.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from vars_gridview.lib.annotation.observation import Observation


class BoundingBoxAssociation:
    """A VARS bounding-box association with local mutation tracking.

    Represents the ``bounding box`` association type in Annosaurus.  The
    ``link_value`` field stores a JSON object with at minimum ``x``, ``y``,
    ``width``, and ``height`` integer keys.  Additional metadata keys (e.g.
    ``verifier``, ``confidence``, ``tags``) may also be present.

    Dirty flags (``_dirty_concept``, ``_dirty_part``, ``_dirty_box``) track
    which fields have been modified locally and need to be flushed to
    Annosaurus.

    This model intentionally has no view references.
    """

    def __init__(
        self,
        uuid: UUID,
        data: dict,
        observation: Observation,
        to_concept: str,
    ) -> None:
        """Initialise a :class:`BoundingBoxAssociation`.

        Args:
            uuid: UUID of the association record in Annosaurus.
            data: Parsed ``link_value`` JSON dict.  Must contain integer keys
                ``x``, ``y``, ``width`` (>0), and ``height`` (>0).
            observation: Parent :class:`~vars_gridview.lib.annotation.observation.Observation`.
            to_concept: Value of the association's ``to_concept`` field
                (``"self"`` when the box covers the whole observed concept).

        Raises:
            KeyError: If any of ``x``, ``y``, ``width``, ``height`` is absent.
            ValueError: If coordinates contain non-integer values, width/height
                are not positive, or x/y are negative.
        """
        self._uuid = uuid
        BoundingBoxAssociation.validate_data(data)
        self._data = data
        self._observation = observation
        self._to_concept = to_concept

        # Dirty flags, controls what gets updated in VARS when pushed
        self._dirty_concept = False
        self._dirty_part = False
        self._dirty_box = False

        # Deleted flag
        self._deleted = False

    @staticmethod
    def validate_data(data: dict) -> None:
        """Validate bounding-box coordinate data.

        Args:
            data: Dict that must contain integer keys ``x``, ``y``, ``width``,
                and ``height``.

        Raises:
            KeyError: One or more required keys are absent.
            ValueError: A value is not an integer, width/height ≤ 0, or x/y < 0.
        """
        required_keys = {"x", "y", "width", "height"}
        keys = set(data.keys())
        missing_keys = required_keys - keys
        if missing_keys:
            raise KeyError(
                f"Bounding box data is missing required key(s): {', '.join(missing_keys)}"
            )
        if not all(isinstance(data[key], int) for key in required_keys):
            raise ValueError(
                "Bounding box data must contain integer values for x, y, width, and height."
            )
        if data["width"] <= 0 or data["height"] <= 0:
            raise ValueError("Bounding box width and height must be positive integers.")
        if data["x"] < 0 or data["y"] < 0:
            raise ValueError(
                "Bounding box x and y coordinates must be non-negative integers."
            )

    def update_data(self, **data: dict) -> None:
        """
        Update the bounding box data.

        Args:
            data (dict): Dictionary of data to update.
        """
        unchanged = True
        for key, value in data.items():
            if key in self._data and self._data[key] != value:
                unchanged = False
                break
        self._data.update(data)
        if not unchanged:
            self._dirty_box = True

    @property
    def data(self) -> dict:
        """
        Get the bounding box data.

        Returns:
            dict: The bounding box data.
        """
        return self._data.copy()

    @property
    def uuid(self) -> UUID:
        """
        Get the UUID of the bounding box association.

        Returns:
            UUID: The UUID of the bounding box association.
        """
        return self._uuid

    @property
    def x(self) -> int:
        """
        Get the x-coordinate of the top-left corner.

        Returns:
            int: The x-coordinate of the top-left corner.
        """
        return self._data["x"]

    @property
    def y(self) -> int:
        """
        Get the y-coordinate of the top-left corner.

        Returns:
            int: The y-coordinate of the top-left corner.
        """
        return self._data["y"]

    @property
    def width(self) -> int:
        """
        Get the width of the bounding box.

        Returns:
            int: The width of the bounding box.
        """
        return self._data["width"]

    @property
    def height(self) -> int:
        """
        Get the height of the bounding box.

        Returns:
            int: The height of the bounding box.
        """
        return self._data["height"]

    @property
    def verifier(self) -> Optional[str]:
        """
        Get the verifier of the bounding box.

        Returns:
            Optional[str]: The verifier of the bounding box.
        """
        return self._data.get("verifier", None)

    @property
    def image_reference_uuid(self) -> Optional[UUID]:
        """
        Get the image reference UUID that this association is made on, if present.

        Returns:
            Optional[UUID]: The image reference UUID, or None if not present.
        """
        return self._data.get("image_reference_uuid", None)

    @property
    def observation(self) -> Observation:
        """
        Get the observation associated with the bounding box.

        Returns:
            Observation: The observation associated with the bounding box.
        """
        return self._observation

    @property
    def concept(self) -> str:
        """
        Get the concept of the bounding box. This comes from the parent observation `concept` field.

        Returns:
            str: The concept of the bounding box.
        """
        return self._observation.concept

    @property
    def part(self) -> str:
        """
        Get the part of the bounding box. This comes from the association `to_concept` field.

        If the part is "self", the bounding box refers to the entire observed concept.

        Returns:
            Optional[str]: The part of the bounding box.
        """
        return self._to_concept

    @property
    def text_label(self) -> str:
        """
        Get the text label for the bounding box. This is used for rendering in the application.

        Returns:
            str: The text label for the bounding box.
        """
        if self.part == "self":
            return self.concept

        return f"{self.concept} {self.part}"

    @property
    def xf(self) -> int:
        """
        Get the x-coordinate of the bottom-right corner.

        Returns:
            int: The x-coordinate of the bottom-right corner.
        """
        return self.x + self.width

    @property
    def yf(self) -> int:
        """
        Get the y-coordinate of the bottom-right corner.

        Returns:
            int: The y-coordinate of the bottom-right corner.
        """
        return self.y + self.height

    @property
    def box(self) -> tuple[int, int, int, int]:
        """Bounding-box corners as ``(x, y, xf, yf)``."""
        return self.x, self.y, self.xf, self.yf

    @property
    def verified(self) -> bool:
        """
        Check if the bounding box has been verified.

        Returns:
            bool: True if the bounding box has been verified, False otherwise.
        """
        return self.verifier is not None

    @property
    def deleted(self) -> bool:
        """
        Check if the bounding box has been deleted.

        Returns:
            bool: True if the bounding box has been deleted, False otherwise.
        """
        return self._deleted

    @deleted.setter
    def deleted(self, value: bool) -> None:
        """
        Set the deleted flag.

        Args:
            value (bool): The value to set the deleted flag to.
        """
        self._deleted = value

    def set_concept(self, concept: Optional[str], part: Optional[str]) -> None:
        """
        Set the concept and part. If either is None, it will not be updated.

        Args:
            concept (Optional[str]): The concept to set. If None, it will not be updated.
            part (Optional[str]): The part to set. If None, it will not be updated.
        """
        # Update the parent observation concept
        if concept is not None and concept != self.concept:
            self._observation.concept = concept
            self._dirty_concept = True

        # Update the bounding box to_concept
        if part is not None and part != self.part:
            self._to_concept = part
            self._dirty_part = True

    def set_verified_concept(
        self, concept: Optional[str], part: Optional[str], verifier: str
    ) -> None:
        """
        Set the concept, part, and verifier. If either of concept or part is None, it will not be updated.

        Args:
            concept (Optional[str]): The concept to set. If None, it will not be updated.
            part (Optional[str]): The part to set. If None, it will not be updated.
            verifier (str): The verifier to set.
        """
        # Update the concept & part
        self.set_concept(concept, part)

        # Update the verifier
        if self._data.get("verifier", None) != verifier:
            self._data["verifier"] = verifier
            self._dirty_box = True

    def verify(self, verifier: str) -> None:
        """
        Verify the bounding box.

        Args:
            verifier (str): The verifier to set.
        """
        if self._data.get("verifier", None) != verifier:
            self._data["verifier"] = verifier
            self._dirty_box = True

    def unverify(self) -> None:
        """
        Unverify the bounding box.
        """
        if self.verified:
            del self._data["verifier"]
            self._dirty_box = True

    def mark_for_training(self) -> None:
        """
        Mark the bounding box for training.
        """
        self._data["tags"] = self._data.get("tags", [])
        if "training" not in self._data["tags"]:
            self._data["tags"].append("training")
            self._dirty_box = True

    def unmark_for_training(self) -> None:
        """
        Unmark the bounding box for training.
        """
        if "tags" in self._data and "training" in self._data["tags"]:
            self._data["tags"].remove("training")
            self._dirty_box = True

    @property
    def is_training(self) -> bool:
        """
        Check if the bounding box is marked for training.

        Returns:
            bool: True if the bounding box is marked for training, False otherwise.
        """
        return "tags" in self._data and "training" in self._data["tags"]

    def push_changes(self, observer: Optional[str] = None) -> None:
        """Flush dirty local state back to Annosaurus.

        Deprecated:
            New code should use ``AnnotationService.push_changes()`` instead,
            which provides proper error handling and off-thread execution.

        Args:
            observer: VARS username to record as the observer when the
                observation concept is updated.  Falls back to the global
                settings value when ``None``.
        """
        raise RuntimeError(
            "BoundingBoxAssociation.push_changes() no longer supports legacy "
            "module-level M3 clients. Use AnnotationService.push_changes() "
            "with an injected Annosaurus client instead."
        )


__all__ = ["BoundingBoxAssociation"]
