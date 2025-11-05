from dataclasses import dataclass
from typing import List, Optional

@dataclass
class KeyboardButton:
    text: str

@dataclass
class ReplyKeyboardMarkup:
    keyboard: List[List[KeyboardButton]]
    resize_keyboard: Optional[bool] = None
    one_time_keyboard: Optional[bool] = None

@dataclass
class ReplyKeyboardRemove:
    remove_keyboard: bool = True
    selective: Optional[bool] = None

@dataclass
class MessageEntity:
    type: str
    offset: int
    length: int
    url: Optional[str] = None
    user: Optional['User'] = None
    language: Optional[str] = None
