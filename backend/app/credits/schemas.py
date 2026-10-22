from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class BalanceOut(BaseModel):
    balance: int
    reserved: int
    available: int
    video_cost: int = 10
    total_credited: int
    total_spent: int

class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=100)

class CodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount: int = Field(strict=True, ge=1, le=1000000)
    expires_in_days: int = Field(default=30, strict=True, ge=1, le=365)

class CodeOut(BaseModel):
    id: UUID
    user_id: UUID
    amount: int
    suffix: str
    status: str
    created_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None

class IssuedCode(CodeOut):
    code: str

class CodeList(BaseModel):
    items: list[CodeOut]
    total: int

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    description: str
    amount: int
    balance_after: int
    created_at: datetime

class TransactionList(BaseModel):
    items: list[TransactionOut]
    total: int
