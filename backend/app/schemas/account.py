from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str


class AccountOut(BaseModel):
    id: int
    name: str
    user_id: int

    model_config = {"from_attributes": True}