"""管理后台接口的请求和响应结构。"""

from pydantic import BaseModel, Field

from app.auth.schemas import PASSWORD_MAX, PASSWORD_MIN, UserOut
from app.models import UserRole

from .user_actions import UserAction


class UserActionRequest(BaseModel):
    action: UserAction


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class SetRoleRequest(BaseModel):
    role: UserRole


class AdminUserOut(UserOut):
    video_count: int = 0


class UserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
