from dataclasses import dataclass

@dataclass
class LabeledPrice:
    label: str
    amount: int

@dataclass
class Invoice:
    title: str
    description: str
    start_parameter: str
    currency: str
    total_amount: int

@dataclass
class SuccessfulPayment:
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
