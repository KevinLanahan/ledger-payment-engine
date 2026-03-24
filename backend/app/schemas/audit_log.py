from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: int | None = None
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}