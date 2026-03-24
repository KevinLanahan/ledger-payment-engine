from datetime import datetime

from pydantic import BaseModel, Field, constr


class LedgerEntryCreate(BaseModel):
    account_id: int
    amount_cents: int = Field(
        ...,
        description="Signed amount in cents. Example: -525 for -$5.25",
    )
    currency: constr(min_length=3, max_length=3) = "USD"
    memo: str | None = None


class TransactionCreate(BaseModel):
    type: str = Field(
        ...,
        description="deposit | withdraw | transfer | journal",
    )
    description: str | None = None
    currency: constr(min_length=3, max_length=3) = "USD"
    entries: list[LedgerEntryCreate]


class LedgerEntryOut(BaseModel):
    id: int
    account_id: int
    amount_cents: int
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionOut(BaseModel):
    id: int
    user_id: int
    type: str
    status: str
    idempotency_key: str
    description: str | None = None
    created_at: datetime
    entries: list[LedgerEntryOut]

    model_config = {"from_attributes": True}


class AccountTransactionOut(BaseModel):
    transaction_id: int
    type: str
    status: str
    idempotency_key: str
    description: str | None = None
    created_at: datetime
    net_amount_cents: int
    entries: list[LedgerEntryOut]