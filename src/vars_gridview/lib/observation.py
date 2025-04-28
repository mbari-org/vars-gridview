from uuid import UUID
from pydantic import BaseModel


class Observation(BaseModel):
    """
    Model for storing observation data.
    """

    uuid: UUID
    concept: str
    observer: str
    group: str
    imaged_moment_uuid: UUID
