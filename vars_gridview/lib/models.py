from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID


@dataclass
class AncillaryData:
    depth_meters: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    oxygen_ml_per_l: Optional[float] = None
    pressure_dbar: Optional[float] = None
    salinity: Optional[float] = None
    temperature_celsius: Optional[float] = None
    light_transmission: Optional[float] = None


@dataclass
class Association:
    uuid: UUID
    
    link_name: str
    to_concept: str
    link_value: str
    
    observation: Optional["Observation"] = None


@dataclass
class ImageReference:
    uuid: UUID
    
    url: str
    format: str
    
    imaged_moment: Optional["ImagedMoment"] = None


@dataclass
class Observation:
    uuid: UUID
    
    concept: str
    observer: str
    
    associations: List[Association] = field(default_factory=list)
    
    imaged_moment: Optional["ImagedMoment"] = None


@dataclass
class ImagedMoment:
    uuid: UUID
    
    recorded_timestamp: Optional[datetime]
    elapsed_time_millis: Optional[int]
    timecode: Optional[str]
    
    observations: List[Observation] = field(default_factory=list)
    image_references: List[ImageReference] = field(default_factory=list)
    ancillary_data: AncillaryData = field(default_factory=AncillaryData)
    
    video_reference: Optional["VideoReference"] = None


@dataclass
class VideoReference:
    uuid: UUID
    
    uri: str
    container: str
    video_codec: str
    width: int
    height: int
    frame_rate: float
    size_bytes: int
    sha512: str
    
    imaged_moments: List[ImagedMoment] = field(default_factory=list)
    
    video: Optional["Video"] = None


@dataclass
class Video:
    uuid: UUID
    
    start_timestamp: datetime
    duration_millis: int
    
    video_references: List[VideoReference] = field(default_factory=list)
    
    video_sequence: Optional["VideoSequence"] = None


@dataclass
class VideoSequence:
    uuid: UUID
    
    name: str
    camera_id: str
    
    videos: List[Video] = field(default_factory=list)
