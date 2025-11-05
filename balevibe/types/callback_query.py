from dataclasses import dataclass
from typing import Optional
from .user import User
from .message import Message

@dataclass
class CallbackQuery:
    id: str
    from_user: User
    message: Optional[Message] = None
    data: Optional[str] = None
