"""注册、登录接口的请求和响应结构。"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UserGender, UserRole, UserStatus

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]+$")
USERNAME_MIN, USERNAME_MAX = 3, 32
PASSWORD_MIN, PASSWORD_MAX = 8, 128
# 登录时用户名还没去空格，比注册上限宽一些；只为挡住超长输入（否则会原样写进 Redis 的计数 key）
LOGIN_USERNAME_MAX = 64


def normalize_username(raw: str) -> str:
    """只去掉首尾空格，保留大小写用于显示；比较时再统一转小写。"""
    return raw.strip()


def check_username(raw: str) -> str:
    """规范化并校验用户名，返回规范化后的值；不合规则抛 ValueError。"""
    v = normalize_username(raw)
    if not USERNAME_MIN <= len(v) <= USERNAME_MAX:
        raise ValueError(f"用户名长度需为 {USERNAME_MIN}–{USERNAME_MAX} 位")
    if not USERNAME_PATTERN.fullmatch(v):
        raise ValueError("用户名只能包含字母、数字、下划线和汉字")
    return v


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        return check_username(v)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=LOGIN_USERNAME_MAX)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class UserOut(UserSummary):
    display_name: str | None = None
    gender: UserGender = UserGender.unspecified
    school: str | None = None
    avatar_url: str | None = None
