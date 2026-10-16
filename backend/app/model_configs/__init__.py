"""模型配置：各用途的接口地址、加密保存的 API key、模型名称，以及配音音色。"""

from .router import router
from .schemas import ModelConfigUpdate, ModelConfigView, ResolvedConfig, Voice
from .service import (
    DEFAULTS,
    list_configs,
    list_voices,
    record_test,
    resolve,
    system_available,
    update_config,
)

__all__ = [
    "DEFAULTS",
    "ModelConfigUpdate",
    "ModelConfigView",
    "ResolvedConfig",
    "Voice",
    "list_configs",
    "list_voices",
    "record_test",
    "resolve",
    "router",
    "system_available",
    "update_config",
]
