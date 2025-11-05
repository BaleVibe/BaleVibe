from dataclasses import dataclass
from typing import List, Optional

@dataclass
class InlineKeyboardButton:
    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None

@dataclass
class InlineKeyboardMarkup:
    inline_keyboard: List[List[InlineKeyboardButton]]
