"""
VARS bounding box association.
"""

from typing import TYPE_CHECKING, Optional, Tuple
from uuid import UUID

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.m3.operations import (
    update_bounding_box_data,
    update_bounding_box_part,
    update_observation_concept,
)
from vars_gridview.lib.observation import Observation

if TYPE_CHECKING:
    from vars_gridview.ui.RectWidget import RectWidget


class BoundingBoxAssociation:
    """
    VARS bounding box association.
    """

    def __init__(
        self,
        uuid: UUID,
        data: dict,
        observation: Observation,
        to_concept: str,
    ):
        """
        Initialize the bounding box association.

        Args:
            uuid (UUID): The UUID of the bounding box association.
            data (dict): The bounding box data.
            observation (Observation): The observation associated with the bounding box.
            to_concept (str): The to_concept field of the bounding box association.

        Raises:
            KeyError: If required keys are missing in the data.
            ValueError: If values are not integers or if width/height are not positive.
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

        # Back-reference
        self.rect_widget: Optional["RectWidget"] = None

    @staticmethod
    def validate_data(data: dict) -> None:
        """
        Validate the bounding box data.

        Args:
            data (dict): The bounding box data to validate.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If values are not integers or if width/height are not positive.
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
        return self._data.get("x")

    @property
    def y(self) -> int:
        """
        Get the y-coordinate of the top-left corner.

        Returns:
            int: The y-coordinate of the top-left corner.
        """
        return self._data.get("y")

    @property
    def width(self) -> int:
        """
        Get the width of the bounding box.

        Returns:
            int: The width of the bounding box.
        """
        return self._data.get("width")

    @property
    def height(self) -> int:
        """
        Get the height of the bounding box.

        Returns:
            int: The height of the bounding box.
        """
        return self._data.get("height")

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
    def box(self) -> Tuple[int, int, int, int]:
        """
        Get the bounding box coordinates as a tuple.

        Returns:
            Tuple[int, int, int, int]: The bounding box coordinates: (x, y, xf, yf).
        """
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

    def push_changes(self) -> None:
        """
        Push any needed changes to VARS. Uses dirty flags to determine what to update.
        """
        # Guard against pushing changes to deleted bounding boxes
        if self._deleted:
            return

        do_modify_box = False

        username = SETTINGS.username.value

        # Updae the observation concept
        if self._dirty_concept:
            update_observation_concept(self._observation.uuid, self.concept, username)
            self._dirty_concept = False
            do_modify_box = True

        # Update the bounding box association part
        if self._dirty_part:
            update_bounding_box_part(self._uuid, self.part)
            self._dirty_part = False
            do_modify_box = True

        # Update the bounding box metadata if the box is dirty
        if self._dirty_box:
            # self._data["generator"] = "gridview"  # Only changes when box moved/resized
            # self._data["observer"] = username
            self._dirty_box = False
            do_modify_box = True

        # Update the bounding box if needed
        if do_modify_box:
            update_bounding_box_data(self._uuid, self.data)
