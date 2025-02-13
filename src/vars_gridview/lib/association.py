"""
VARS bounding box association.
"""

import json
from typing import Optional, Union

import cv2
import numpy as np
import requests

from vars_gridview.lib.constants import SKIMMER_URL
from vars_gridview.lib.m3.operations import (
    update_bounding_box_data,
    update_bounding_box_part,
    update_observation_concept,
)


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

        # Dreaded back-reference
        self.rect = None

    @staticmethod
    def from_json(data: Union[str, dict]):
        if isinstance(data, str):
            data = json.loads(data)

        return BoundingBoxAssociation(**data)

    @property
    def json(self):
        return {
            "x": self._x,
            "y": self._y,
            "width": self._width,
            "height": self._height,
            "image_reference_uuid": self.image_reference_uuid,
            **self.meta,
        }

    @property
    def json_str(self):
        return json.dumps(self.json)

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

    def get_roi(self, image_url: str) -> np.ndarray:
        """
        Get the region of interest from the image at the given URL.

        Args:
            image_url (str): The URL of the image.

        Returns:
            np.ndarray: The region of interest.
        """
        # Call Skimmer
        response = requests.get(
            f"{SKIMMER_URL}/crop",
            params={
                "url": image_url,
                "left": self._x,
                "top": self._y,
                "right": self.xf,
                "bottom": self.yf,
            },
        )
        response.raise_for_status()

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

    def push_changes(self, verifier: str):
        if self._deleted:
            return

        do_modify_box = False

        if self._dirty_concept:
            update_observation_concept(self.observation_uuid, self._concept, verifier)
            self._dirty_concept = False
            do_modify_box = True

        if self._dirty_part:
            update_bounding_box_part(self.association_uuid, self._part)
            self._dirty_part = False
            do_modify_box = True

        if self._dirty_box:
            self.meta["generator"] = "gridview"  # Only changes when box moved/resized
            self.meta["observer"] = verifier
            self._dirty_box = False
            do_modify_box = True

        if self._dirty_verifier:
            do_modify_box = True
            self._dirty_verifier = False

        if do_modify_box:
            update_bounding_box_data(self.association_uuid, self.json)
