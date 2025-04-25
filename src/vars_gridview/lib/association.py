"""
VARS bounding box association.
"""

import json
from typing import TYPE_CHECKING, Optional, Tuple

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.m3.operations import (
    update_bounding_box_data,
    update_bounding_box_part,
    update_observation_concept,
)

if TYPE_CHECKING:
    from vars_gridview.ui.RectWidget import RectWidget


class BoundingBoxAssociation:
    """
    VARS bounding box association.
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        image_reference_uuid: Optional[str] = None,
        **meta,
    ):
        """
        Initialize the bounding box association.

        Args:
            x (int): The x-coordinate of the top-left corner.
            y (int): The y-coordinate of the top-left corner.
            width (int): The width of the bounding box.
            height (int): The height of the bounding box.
            image_reference_uuid (Optional[str]): Image reference UUID of the framegrab that the bounding box association is linked to. Defaults to None (in the case of video-made bounding boxes).
        """
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self.image_reference_uuid = image_reference_uuid
        self.observation_uuid = None
        self.association_uuid = None
        self.imaged_moment_uuid = None
        self.meta = meta
        self._concept = None
        self._part = None

        # Dirty flags, controls what gets updated in VARS when pushed
        self._dirty_concept = False
        self._dirty_part = False
        self._dirty_box = False
        self._dirty_verifier = False

        # Deleted flag
        self._deleted = False

        # Back-reference
        self.rect_widget: Optional["RectWidget"] = None

    @classmethod
    def from_json(cls, data: str) -> "BoundingBoxAssociation":
        """
        Parse a JSON string into a bounding box association object.

        Args:
            data (str): JSON string to parse.

        Returns:
            BoundingBoxAssociation: Parsed bounding box association object.
        """
        if isinstance(data, str):
            data = json.loads(data)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "BoundingBoxAssociation":
        """
        Parse a dictionary into a bounding box association object.

        Args:
            data (dict): Dictionary to parse.

        Returns:
            BoundingBoxAssociation: Parsed bounding box association object.
        """
        return cls(**data)

    def to_dict(self) -> dict:
        """
        Convert the bounding box association to a dictionary.
        This is what populates the VARS bounding box association `link_value` field.

        Returns:
            dict: The bounding box association as a dictionary.
        """
        d = {
            "x": self._x,
            "y": self._y,
            "width": self._width,
            "height": self._height,
        }

        # Only add the image reference UUID if it is not None
        if self.image_reference_uuid is not None:
            d["image_reference_uuid"] = self.image_reference_uuid

        d.update(self.meta)

        return d

    def to_json(self) -> str:
        """
        Convert the bounding box association to a JSON string.

        Returns:
            str: The bounding box association as a JSON string.
        """
        return json.dumps(self.to_dict())

    @property
    def x(self) -> int:
        """
        Get the x-coordinate of the top-left corner.

        Returns:
            int: The x-coordinate of the top-left corner.
        """
        return self._x

    @property
    def y(self) -> int:
        """
        Get the y-coordinate of the top-left corner.

        Returns:
            int: The y-coordinate of the top-left corner.
        """
        return self._y

    @property
    def width(self) -> int:
        """
        Get the width of the bounding box.

        Returns:
            int: The width of the bounding box.
        """
        return self._width

    @property
    def height(self) -> int:
        """
        Get the height of the bounding box.

        Returns:
            int: The height of the bounding box.
        """
        return self._height

    @property
    def concept(self) -> Optional[str]:
        """
        Get the concept of the bounding box. This comes from the parent observation `concept` field.

        Returns:
            Optional[str]: The concept of the bounding box.
        """
        return self._concept

    @property
    def part(self) -> Optional[str]:
        """
        Get the part of the bounding box. This comes from the association `to_concept` field.

        If the part is "self", the bounding box refers to the entire observed concept.

        Returns:
            Optional[str]: The part of the bounding box.
        """
        return self._part

    @property
    def text_label(self) -> str:
        """
        Get the text label for the bounding box. This is used for rendering in the application.

        Returns:
            str: The text label for the bounding box.
        """
        if self._part == "self":
            return self._concept

        return "{} {}".format(self._concept, self._part)

    @property
    def xf(self) -> int:
        """
        Get the x-coordinate of the bottom-right corner.

        Returns:
            int: The x-coordinate of the bottom-right corner.
        """
        return self._x + self._width

    @property
    def yf(self) -> int:
        """
        Get the y-coordinate of the bottom-right corner.

        Returns:
            int: The y-coordinate of the bottom-right corner.
        """
        return self._y + self._height

    @property
    def box(self) -> Tuple[int, int, int, int]:
        """
        Get the bounding box coordinates as a tuple.

        Returns:
            Tuple[int, int, int, int]: The bounding box coordinates: (x, y, xf, yf).
        """
        return self._x, self._y, self.xf, self.yf

    @property
    def verified(self) -> bool:
        """
        Check if the bounding box has been verified.

        Returns:
            bool: True if the bounding box has been verified, False otherwise.
        """
        return "verifier" in self.meta

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

    def set_box(self, x: int, y: int, width: int, height: int) -> None:
        """
        Set the bounding box.

        Args:
            x (int): x-coordinate of the top-left corner.
            y (int): y-coordinate of the top-left corner.
            width (int): width of the bounding box.
            height (int): height of the bounding box.
        """
        if self.x != x or self.y != y or self.width != width or self.height != height:
            self._dirty_box = True

        self._x = int(x)
        self._y = int(y)
        self._width = int(width)
        self._height = int(height)

    def set_concept(self, concept: Optional[str], part: Optional[str]) -> None:
        """
        Set the concept and part. If either is None, it will not be updated.

        Args:
            concept (Optional[str]): The concept to set. If None, it will not be updated.
            part (Optional[str]): The part to set. If None, it will not be updated.
        """
        if self._concept is not None and concept != self._concept:
            self._dirty_concept = True

        if self._part is not None and part != self._part:
            self._dirty_part = True

        self._concept = concept
        self._part = part

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
        self.set_concept(concept, part)
        self.meta["verifier"] = verifier
        self._dirty_verifier = True

    def unverify(self) -> None:
        """
        Unverify the bounding box.
        """
        if self.verified:
            del self.meta["verifier"]
            self._dirty_verifier = True

    def mark_for_training(self) -> None:
        """
        Mark the bounding box for training.
        """
        self.meta["tags"] = self.meta.get("tags", [])
        if "training" not in self.meta["tags"]:
            self.meta["tags"].append("training")
            self._dirty_box = True

    def unmark_for_training(self) -> None:
        """
        Unmark the bounding box for training.
        """
        if "tags" in self.meta and "training" in self.meta["tags"]:
            self.meta["tags"].remove("training")
            self._dirty_box = True

    @property
    def is_training(self) -> bool:
        """
        Check if the bounding box is marked for training.

        Returns:
            bool: True if the bounding box is marked for training, False otherwise.
        """
        return "tags" in self.meta and "training" in self.meta["tags"]

    @property
    def is_box_valid(self) -> bool:
        """
        Check if the bounding box is valid.

        Returns:
            bool: True if the bounding box is valid, False otherwise.
        """
        return self.xf > self.x and self.yf > self.y

    def is_in_bounds(self, min_x: int, min_y: int, max_x: int, max_y: int) -> bool:
        """
        Check if the bounding box is within the given bounds.

        Args:
            min_x (int): Minimum x-coordinate.
            min_y (int): Minimum y-coordinate.
            max_x (int): Maximum x-coordinate.
            max_y (int): Maximum y-coordinate.

        Returns:
            bool: True if the bounding box is within the given bounds, False otherwise.
        """
        return (
            self.x >= min_x
            and self.y >= min_y
            and self.xf <= max_x
            and self.yf <= max_y
        )

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
            update_observation_concept(self.observation_uuid, self._concept, username)
            self._dirty_concept = False
            do_modify_box = True

        # Update the bounding box association part
        if self._dirty_part:
            update_bounding_box_part(self.association_uuid, self._part)
            self._dirty_part = False
            do_modify_box = True

        # Update the bounding box metadata if the box is dirty
        if self._dirty_box:
            self.meta["generator"] = "gridview"  # Only changes when box moved/resized
            self.meta["observer"] = username
            self._dirty_box = False
            do_modify_box = True

        # Update the verifier if the verifier is dirty
        if self._dirty_verifier:
            do_modify_box = True
            self._dirty_verifier = False

        # Update the bounding box if needed
        if do_modify_box:
            update_bounding_box_data(self.association_uuid, self.to_dict())
