"""
rectlabel.py -- Tools to implement a labeling UI for bounding boxes in images
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.
"""

import json
from typing import Optional, Union

import numpy as np

from vars_gridview.lib.m3.operations import (
    delete_association,
    update_bounding_box_data,
    update_bounding_box_part,
    update_observation_concept,
)


class VARSLocalization:
    """Representation of VARS localizations (bounding boxes)"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        image_reference_uuid: Optional[str] = None,
        **meta
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
        if type(data) == str:
            data = json.loads(data)

        return VARSLocalization(**data)

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

    def get_roi(self, image: np.ndarray):
        return image[self._y : self.yf, self._x : self.xf]

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
