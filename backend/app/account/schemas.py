from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.schemas import PASSWORD_MAX, PASSWORD_MIN
from app.models import UserGender


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=40)
    gender: UserGender | None = None
    school: str | None = Field(default=None, max_length=100)

    @field_validator("display_name", "school")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @field_validator("gender")
    @classmethod
    def gender_cannot_be_null(cls, value: UserGender | None) -> UserGender:
        if value is None:
            raise ValueError("请选择性别，或选择不愿透露")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX, repr=False)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX, repr=False)
