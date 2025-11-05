from dataclasses import dataclass
from typing import Optional

@dataclass
class Sticker:
    file_id: str
    width: int
    height: int
    is_animated: bool
    thumb: Optional['PhotoSize'] = None
    emoji: Optional[str] = None
    set_name: Optional[str] = None
    mask_position: Optional[str] = None
    file_size: Optional[int] = None
