from dataclasses import dataclass
from typing import Optional
from .photo_size import PhotoSize

@dataclass
class Animation:
    file_id: str
    width: int
    height: int
    duration: int
    thumb: Optional[PhotoSize] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
