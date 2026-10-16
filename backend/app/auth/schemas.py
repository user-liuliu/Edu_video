"""注册、登录接口的请求和响应结构。"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UserRole, UserStatus

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]+$")
USERNAME_MIN, USERNAME_MAX = 3, 32
PASSWORD_MIN, PASSWORD_MAX = 8, 128


def normalize_username(raw: str) -> str:
    """只去掉首尾空格，保留大小写用于显示；比较时再统一转小写。"""
    return raw.strip()


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        v = normalize_username(v)
        if not USERNAME_MIN <= len(v) <= USERNAME_MAX:
            raise ValueError(f"用户名长度需为 {USERNAME_MIN}–{USERNAME_MAX} 位")
        if not USERNAME_PATTERN.fullmatch(v):
            raise ValueError("用户名只能包含字母、数字、下划线和汉字")
        return v


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    status: UserStatus
    created_at: datetime
