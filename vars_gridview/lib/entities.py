"""
Entity dataclasses for the M3 database schema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from vars_gridview.lib.util import get_timestamp, parse_timestamp


# M3_ANNOTATIONS

@dataclass
class ImagedMoment:
    uuid: UUID  # PK
    
    # Fields
    elapsed_time_millis: Optional[int] = None
    recorded_timestamp: Optional[datetime] = None
    timecode: Optional[str] = None
    
    # Parent entity
    video_reference: Optional['VideoReference'] = None
    
    # Child entities
    ancillary_data: List['AncillaryData'] = field(default_factory=list)
    observations: List['Observation'] = field(default_factory=list)
    image_references: List['ImageReference'] = field(default_factory=list)
    
    def add_ancillary_data(self, ancillary_data: 'AncillaryData'):
        self.ancillary_data.append(ancillary_data)
        ancillary_data.imaged_moment = self
    
    def add_observation(self, observation: 'Observation'):
        self.observations.append(observation)
        observation.imaged_moment = self
    
    def add_image_reference(self, image_reference: 'ImageReference'):
        self.image_references.append(image_reference)
        image_reference.imaged_moment = self
    
    def get_timestamp(self) -> Optional[datetime]:
        """
        Get the timestamp of this imaged moment as a datetime. Returns None if the timestamp could not be determined.
        
        Raises:
            ValueError: If this imaged moment has no video reference.
        """
        if self.video_reference is None:
            raise ValueError("ImagedMoment has no video reference")
        
        return get_timestamp(
            video_start_timestamp=self.video_reference.video.start_time,
            recorded_timestamp=self.recorded_timestamp,
            elapsed_time_millis=self.elapsed_time_millis,
            timecode=self.timecode,
        )


@dataclass
class Observation:
    uuid: UUID  # PK
    
    # Fields
    activity: Optional[str] = None
    concept: Optional[str] = None
    duration_millis: Optional[int] = None
    observation_group: Optional[str] = None
    observer: Optional[str] = None
    
    # Parent entity
    imaged_moment: Optional[ImagedMoment] = None
    
    # Child entities
    associations: List['Association'] = field(default_factory=list)
    
    def add_association(self, association: 'Association'):
        self.associations.append(association)
        association.observation = self


@dataclass
class Association:
    uuid: UUID  # PK
    
    # Fields
    link_name: str
    to_concept: str
    link_value: str
    mime_type: Optional[str] = None
    
    # Parent entity
    observation: Optional[Observation] = None


@dataclass
class ImageReference:
    uuid: UUID  # PK
    
    # Fields
    url: Optional[str] = None
    format: Optional[str] = None
    description: Optional[str] = None
    width_pixels: Optional[int] = None
    height_pixels: Optional[int] = None
    
    # Parent entity
    imaged_moment: Optional[ImagedMoment] = None
    
    @classmethod
    def from_m3_dict(cls, image_reference_dict: dict) -> 'ImageReference':
        """
        Construct an ImageReference from a dict fetched via M3. See vars_gridview.lib.m3.operations.get_image_reference().
        
        Args:
            image_reference_dict: Dict containing image reference data.
        
        Returns:
            Constructed ImageReference.
        
        Raises:
            KeyError: If the dict does not contain the required fields.
        """
        return cls(
            uuid=UUID(image_reference_dict["uuid"]),
            url=image_reference_dict["url"],
            format=image_reference_dict["format"],
            description=image_reference_dict["description"],
            width_pixels=image_reference_dict["width_pixels"],
            height_pixels=image_reference_dict["height_pixels"],
        )


@dataclass
class AncillaryData:
    uuid: UUID
    
    # Fields
    # TODO: Add fields
    
    # Parent entity
    imaged_moment: Optional[ImagedMoment] = None


# M3_VIDEO_ASSETS

@dataclass
class VideoSequence:
    uuid: UUID  # PK
    
    # Fields
    camera_id: Optional[str] = None
    description: Optional[str] = None
    name: Optional[str] = None
    
    # Child entities
    videos: List['Video'] = field(default_factory=list)
    
    def add_video(self, video: 'Video'):
        self.videos.append(video)
        video.video_sequence = self


@dataclass
class Video:
    uuid: UUID  # PK
    
    # Fields
    start_time: Optional[datetime] = None
    duration_millis: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    
    # Parent entity
    video_sequence: Optional[VideoSequence] = None
    
    # Child entities
    video_references: List['VideoReference'] = field(default_factory=list)
    
    def add_video_reference(self, video_reference: 'VideoReference'):
        self.video_references.append(video_reference)
        video_reference.video = self
    
    def get_start_timestamp(self) -> Optional[datetime]:
        """
        Get the start timestamp of this video as a datetime. Returns None if the start timestamp could not be determined.
        
        Raises:
            ValueError: If this video has no start time.
        """
        if self.start_time is None:
            raise ValueError("Video has no start time")
        
        return parse_timestamp(self.start_time)
    
    def get_end_timestamp(self) -> Optional[datetime]:
        """
        Get the end timestamp of this video as a datetime. Returns None if the end timestamp could not be determined.
        
        Raises:
            ValueError: If this video has no start time or duration.
        """
        if self.start_time is None:
            raise ValueError("Video has no start time")
        if self.duration_millis is None:
            raise ValueError("Video has no duration")
        
        return get_timestamp(
            video_start_timestamp=self.start_time,
            elapsed_time_millis=self.duration_millis,
        )


@dataclass
class VideoReference:
    uuid: UUID  # PK
    
    # Fields
    uri: Optional[str] = None
    container: Optional[str] = None
    
    # Parent entity
    video: Optional[Video] = None
