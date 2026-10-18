from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    title: str = Field(default='', max_length=200)
    form_values: dict[str, Any] = Field(default_factory=dict)
    form_version: str | None = None

    @field_validator('prompt')
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('请填写想讲什么')
        return value


class ProjectUpdate(ProjectCreate):
    revision: int = Field(ge=1)


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    prompt: str
    form_values: dict[str, Any]
    status: str
    revision: int
    needs_regeneration: bool
    created_at: datetime
    updated_at: datetime


class ProjectList(BaseModel):
    items: list[ProjectView]
    total: int
