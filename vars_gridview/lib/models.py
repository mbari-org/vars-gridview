"""
VARS GridView internal data models.
"""

import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

from vars_gridview.lib.entities import Association


@dataclass
class BoundingBox:
    
    class MalformedBoundingBoxError(Exception):
        """
        Raised when a bounding box JSON is malformed.
        """
        pass
    
    x: Union[int, float]
    y: Union[int, float]
    width: Union[int, float]
    height: Union[int, float]
    association: Association
    metadata: dict = field(default_factory=dict)
    
    def round(self):
        """
        Round the bounding box coordinates to the nearest integer.
        """
        self.x = round(self.x)
        self.y = round(self.y)
        self.width = round(self.width)
        self.height = round(self.height)
    
    def scale(self, x_scale: float, y_scale: float):
        """
        Scale the bounding box coordinates by the given factors.
        """
        self.x *= x_scale
        self.y *= y_scale
        self.width *= x_scale
        self.height *= y_scale
    
    def offset(self, x_offset: int, y_offset: int):
        """
        Offset the bounding box coordinates by the given amounts.
        """
        self.x += x_offset
        self.y += y_offset
    
    @classmethod
    def from_association(cls, association: Association) -> 'BoundingBox':
        """
        Construct a new AssociationBoundingBox from the given Association.
        """
        x, y, width, height, metadata = cls.parse_box_json(association.link_value)
        return cls(x, y, width, height, association, metadata)
    
    @staticmethod
    def parse_box_json(json_str: str) -> Optional[Tuple[float, float, float, float, dict]]:
        """
        Parse a bounding box JSON string. 
        
        The minimum required fields are `x`, `y`, `width`, and `height`. Additional fields will be returned as a dictionary.
        
        Args:
            json_str: The JSON string to parse.
        
        Returns:
            A tuple of the form (x, y, width, height, fields).
        
        Raises:
            BoundingBox.MalformedBoundingBoxError: If the JSON is malformed.
        
        Examples:
            >>> BoundingBox.parse_box_json('{"x": 0, "y": 0, "width": 100, "height": 100}')
            (0.0, 0.0, 100.0, 100.0, {})
            
            >>> BoundingBox.parse_box_json('{"x": 0, "y": 0, "width": 100, "height": 100, "foo": "bar"}')
            (0.0, 0.0, 100.0, 100.0, {'foo': 'bar'})
        """
        # Parse JSON
        try:
            box = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise BoundingBox.MalformedBoundingBoxError("Bounding box JSON is malformed") from e
        
        # Check for required fields
        required_fields = {"x", "y", "width", "height"}
        if not required_fields.issubset(box.keys()):
            raise BoundingBox.MalformedBoundingBoxError(f"Bounding box JSON is missing required fields: {required_fields - box.keys()}")

        # Get required fields
        try:
            x = float(box["x"])
            y = float(box["y"])
            width = float(box["width"])
            height = float(box["height"])
        except ValueError as e:
            raise BoundingBox.MalformedBoundingBoxError("Bounding box in JSON contains non-numeric dimensional values") from e
        
        # Get remaining fields
        remaining_fields = {k: v for k, v in box.items() if k not in required_fields}
        
        return x, y, width, height, remaining_fields
