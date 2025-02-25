"""
VARS bounding box association.
"""

import json
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.m3.operations import (
    crop,
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
        if isinstance(data, str):
            data = json.loads(data)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "BoundingBoxAssociation":
        return cls(**data)

    def to_dict(self) -> dict:
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
        return json.dumps(self.to_dict())

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def concept(self):
        return self._concept

    @property
    def part(self):
        return self._part

    @property
    def text_label(self):
        if self._part == "self":
            return self._concept

        return "{} {}".format(self._concept, self._part)

    @property
    def xf(self):
        return self._x + self._width

    @property
    def yf(self):
        return self._y + self._height

    @property
    def box(self):
        return self._x, self._y, self.xf, self.yf

    @property
    def verified(self):
        return "verifier" in self.meta

    @property
    def deleted(self):
        return self._deleted

    @deleted.setter
    def deleted(self, value):
        self._deleted = value

    def set_box(self, x: int, y: int, width: int, height: int):
        if self.x != x or self.y != y or self.width != width or self.height != height:
            self._dirty_box = True

        self._x = int(x)
        self._y = int(y)
        self._width = int(width)
        self._height = int(height)

    def set_concept(self, concept: str, part: str):
        if self._concept is not None and concept != self._concept:
            self._dirty_concept = True

        if self._part is not None and part != self._part:
            self._dirty_part = True

        self._concept = concept
        self._part = part

    def set_verified_concept(self, concept, part, verifier):
        self.set_concept(concept, part)
        self.meta["verifier"] = verifier
        self._dirty_verifier = True

    def unverify(self):
        if self.verified:
            del self.meta["verifier"]
            self._dirty_verifier = True

    def get_roi(
        self, image_url: str, elapsed_time_millis: Optional[int] = None
    ) -> np.ndarray:
        """
        Get the region of interest from the image at the given URL.

        Args:
            image_url (str): The URL of the image.
            elapsed_time_millis (int, optional): The elapsed time in milliseconds.

        Returns:
            np.ndarray: The region of interest.

        Raises:
            requests.exceptions.HTTPError: If the request to the Skimmer fails.
        """
        # Get the image from the Skimmer
        response = crop(
            image_url, self.x, self.y, self.xf, self.yf, ms=elapsed_time_millis
        )

        # Decode the image
        image = cv2.imdecode(
            np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR
        )
        return image

    @property
    def valid_box(self):
        return self.xf > self.x and self.yf > self.y

    def in_bounds(self, min_x, min_y, max_x, max_y):
        return (
            self.x >= min_x
            and self.y >= min_y
            and self.xf <= max_x
            and self.yf <= max_y
        )

    def push_changes(self):
        if self._deleted:
            return

        do_modify_box = False

        username = SETTINGS.username.value

        if self._dirty_concept:
            update_observation_concept(self.observation_uuid, self._concept, username)
            self._dirty_concept = False
            do_modify_box = True

        if self._dirty_part:
            update_bounding_box_part(self.association_uuid, self._part)
            self._dirty_part = False
            do_modify_box = True

        if self._dirty_box:
            self.meta["generator"] = "gridview"  # Only changes when box moved/resized
            self.meta["observer"] = username
            self._dirty_box = False
            do_modify_box = True

        if self._dirty_verifier:
            do_modify_box = True
            self._dirty_verifier = False

        if do_modify_box:
            update_bounding_box_data(self.association_uuid, self.to_dict())
