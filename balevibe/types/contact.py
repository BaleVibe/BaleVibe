from dataclasses import dataclass
from typing import Optional

@dataclass
class Contact:
    phone_number: str
    first_name: str
    last_name: Optional[str] = None
    user_id: Optional[int] = None
