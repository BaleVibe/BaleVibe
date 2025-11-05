from dataclasses import dataclass
from typing import Optional
from .user import User

@dataclass
class PreCheckoutQuery:
    id: str
    from_user: User
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: Optional[str] = None
    order_info: Optional[str] = None
