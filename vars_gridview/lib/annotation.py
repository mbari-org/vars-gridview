"""
rectlabel.py -- Tools to implement a labeling UI for bounding boxes in images
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.
"""

import json
from typing import List, Optional, Union

import numpy as np

from vars_gridview.lib.m3.operations import (
    update_association_data_bulk,
    update_bounding_box_data,
    update_bounding_box_part,
    update_observation_concept,
    update_observation_concepts_bulk,
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
        if isinstance(data, str):
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

    def unverify(self):
        if self.verified:
            del self.meta["verifier"]
            self._dirty_verifier = True

    def get_roi(self, image: np.ndarray):
        return image[self._y : self.yf, self._x : self.xf]

    @property
    def valid_box(self):
        return self.xf > self.x and self.yf > self.y

    @property
    def dirty_concept(self):
        return self._dirty_concept

    @property
    def dirty_part(self):
        return self._dirty_part

    @property
    def dirty_box(self):
        return self._dirty_box

    @property
    def dirty_verifier(self):
        return self._dirty_verifier

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


def bulk_update_localizations(localizations: List[VARSLocalization], verifier: str):
    """
    Bulk update localizations. This is a performance optimization to reduce the number of calls to Annosaurus.

    Args:
        localizations: List of VARSLocalization objects
        verifier: User who is performing the update
    """
    if not localizations:
        return

    # We will call two endpoints to update relevant data.
    # PUT annotations/bulk -- for updating observation concept, observer
    # PUT associations/bulk -- for updating part, bounding box data, verifier

    # Find all localizations that have a dirty concept. For those, call PUT annotations/bulk
    to_update_annotation = [
        localization for localization in localizations if localization.dirty_concept
    ]
    observation_uuid_concept_pairs = [
        (localization.observation_uuid, localization.concept)
        for localization in to_update_annotation
    ]

    if observation_uuid_concept_pairs:
        update_observation_concepts_bulk(observation_uuid_concept_pairs, verifier)

    # Remove dirty flags
    for localization in to_update_annotation:
        localization._dirty_concept = False

    # Find all localizations that have a dirty part or dirty box. For those, call PUT associations/bulk
    to_update_associations = [
        localization
        for localization in localizations
        if localization.dirty_part
        or localization.dirty_box
        or localization.dirty_verifier
    ]

    # Update the observer and generator as needed
    to_update_observer = [
        localization
        for localization in to_update_associations
        if localization.dirty_box
    ]
    for localization in to_update_observer:
        localization.meta["observer"] = verifier
        localization.meta["generator"] = "gridview"

    request_data = [
        {
            "uuid": localization.association_uuid,
            "link_name": "bounding box",
            "to_concept": localization.part,
            "link_value": json.dumps(localization.json),
            "mime_type": "application/json",
        }
        for localization in to_update_associations
    ]

    if request_data:
        update_association_data_bulk(request_data)

    # Remove dirty flags
    for localization in to_update_associations:
        localization._dirty_part = False
        localization._dirty_box = False
        localization._dirty_verifier = False
