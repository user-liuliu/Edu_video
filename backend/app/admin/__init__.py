"""管理后台：用户管理与系统设置。"""

from .settings_router import router as settings_router
from .user_actions import (
    LAST_ADMIN_MESSAGE,
    UserAction,
    apply_user_action,
    reset_password,
    set_role,
)
from .users_router import router as users_router

__all__ = [
    "LAST_ADMIN_MESSAGE",
    "UserAction",
    "apply_user_action",
    "reset_password",
    "set_role",
    "settings_router",
    "users_router",
]
