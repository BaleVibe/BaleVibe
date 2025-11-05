from dataclasses import dataclass
from typing import Optional, List

from .user import User
from .chat import Chat

@dataclass
class Message:
    message_id: int
    from_user: Optional[User]
    date: int
    chat: Chat
    text: Optional[str] = None
