from datetime import datetime

from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount_cents: int = Field(..., gt=0, description="Positive integer amount in cents")
    description: str | None = None


class TransferLedgerEntryOut(BaseModel):
    id: int
    account_id: int
    amount_cents: int
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferOut(BaseModel):
    transaction_id: int
    user_id: int
    type: str
    status: str
    idempotency_key: str
    description: str | None = None
    created_at: datetime
    from_account_id: int
    to_account_id: int
    amount_cents: int
    entries: list[TransferLedgerEntryOut]