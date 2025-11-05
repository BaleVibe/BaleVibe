from dataclasses import dataclass
from typing import Optional
from .photo_size import PhotoSize

@dataclass
class Document:
    file_id: str
    thumb: Optional[PhotoSize] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
