"""
Entity dataclasses for the M3 database schema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID


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


@dataclass
class VideoReference:
    uuid: UUID  # PK
    
    # Fields
    uri: Optional[str] = None
    container: Optional[str] = None
    
    # Parent entity
    video: Optional[Video] = None
