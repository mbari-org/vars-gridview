"""
VARS GridView internal data models.
"""

from abc import ABC, abstractmethod
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

import cv2
import requests
import numpy as np
from beholder_client import BeholderClient

from vars_gridview.lib.entities import Association, ImageReference, ImagedMoment, VideoReference


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
    image_source: 'ImageSource' = None
    
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


class ImageSource(ABC):
    """
    Image source wrapper abstract base class.
    """
    
    class ImageRetrievalException(Exception):
        """
        Raised when an image cannot be retrieved.
        """
        pass
    
    class MalformedImageException(Exception):
        """
        Raised when a decoded image is malformed.
        """
        pass
    
    def __init__(self, display_scale_x: float = 1.0, display_scale_y: float = 1.0) -> None:
        self.display_scale_x = display_scale_x
        self.display_scale_y = display_scale_y
        
        self._data = None
    
    @property
    @abstractmethod
    def url(self) -> str:
        """
        Get the image URL.
        """
        raise NotImplementedError()
    
    @property
    @abstractmethod
    def width(self) -> int:
        """
        Get the image width in pixels.
        """
        raise NotImplementedError()
    
    @property
    @abstractmethod
    def height(self) -> int:
        """
        Get the image height in pixels.
        """
        raise NotImplementedError()
    
    @property
    def data(self) -> bytes:
        """
        Get the image data. This is cached after the first call.
        
        Raises:
            ImageSource.ImageRetrievalException: If the image data cannot be retrieved.
        """
        if self._data is None:
            try:
                self._data = self._get_data()
            except Exception as e:
                raise ImageSource.ImageRetrievalException("Image data could not be retrieved") from e
        return self._data
    
    def get_display_image(self) -> np.ndarray:
        """
        Decode the image data into a numpy array using cv::imdecode, and scale it according to the display scale factors. This uses the cached image data, if available.
        
        Note: the dimensions of this image do not necessarily match the dimensions specified by the source Image.width, Image.height.
        
        Returns:
            The decoded image as a numpy array.
        
        Raises:
            ImageSource.ImageRetrievalException: If the image data cannot be retrieved.
            ImageSource.MalformedImageException: If the image data is malformed.
        """
        data = self.data
        
        try:
            arr = np.fromstring(data, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            raise ImageSource.MalformedImageException("Image data could not be decoded") from e
    
    def _get_data(self) -> bytes:
        """
        Get the image data.
        
        This can be overridden by subclasses to control how the data is retrieved. By default, this uses a GET request to the image URL with chunked transfer encoding.
        
        Returns:
            The image data as a bytes object.
        
        Raises:
            requests.HTTPError: If the request fails.
        """
        with requests.get(self.url, stream=True) as res:
            res.raise_for_status()
            return res.content
    
    @property
    def display_width(self) -> int:
        """
        Get the image width in pixels, scaled by the x display scale factor.
        """
        return round(self.width * self.display_scale_x)
    
    @property
    def display_height(self) -> int:
        """
        Get the image height in pixels, scaled by the y display scale factor.
        """
        return round(self.height * self.display_scale_y)


class ImageReferenceImageSource(ImageSource):
    """
    Image source wrapper for an ImageReference.
    """
    
    def __init__(self, image_reference: ImageReference, display_scale_x: float = 1, display_scale_y: float = 1) -> None:
        super().__init__(display_scale_x, display_scale_y)
        
        self._image_reference = image_reference
    
    @property
    def url(self) -> str:
        return self._image_reference.url
    
    @property
    def width(self) -> int:
        return self._image_reference.width_pixels
    
    @property
    def height(self) -> int:
        return self._image_reference.height_pixels


class BeholderImageSource(ImageSource):
    """
    Image source wrapper for a video frame to be captured via Beholder.
    """
    
    def __init__(self, beholder_client: BeholderClient, video_reference: VideoReference, imaged_moment: ImagedMoment, display_scale_x: float = 1, display_scale_y: float = 1) -> None:
        super().__init__(display_scale_x, display_scale_y)
        
        self._beholder_client = beholder_client
        self._video_reference = video_reference
        self._imaged_moment = imaged_moment
    
    @property
    def url(self) -> str:
        raise NotImplementedError("BeholderImageSource does not have a URL")
    
    @property
    def width(self) -> int:
        if self._video_reference.video is not None:
            return self._video_reference.video.width
        
        raise ValueError("VideoReference has no video")
    
    @property
    def height(self) -> int:
        if self._video_reference.video is not None:
            return self._video_reference.video.height
        
        raise ValueError("VideoReference has no video")
    
    def _get_data(self) -> bytes:
        """
        Use Beholder to capture the frame.
        """
        if not self._video_reference.uri:
            raise ValueError("VideoReference has no URI")
        if not self._video_reference.uri.lower().endswith(".mp4"):  # guard against bad URIs
            raise ValueError(f"VideoReference URI does not end with .mp4 or .MP4: {self._video_reference.uri}. GridView's use of Beholder only supports MP4s.")
        
        # Get the provided video start timestamp
        try:
            video_start_timestamp = self._video_reference.video.get_start_timestamp()
        except ValueError as e:
            raise ValueError("Could not get video start timestamp") from e
        
        # Get the imaged moment timestamp
        try:
            imaged_moment_timestamp = self._imaged_moment.get_timestamp()
        except ValueError as e:
            raise ValueError("Could not get imaged moment timestamp") from e
        
        # Get the video reference relative elapsed time in milliseconds
        video_reference_relative_elapsed_time_millis = round((imaged_moment_timestamp - video_start_timestamp).total_seconds() * 1000)
        
        # Capture the frame
        return self._beholder_client.capture_raw(self._video_reference.uri, video_reference_relative_elapsed_time_millis)
