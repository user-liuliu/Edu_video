"""模型配置的数据结构：管理后台的展示 / 修改格式，以及给业务代码用的解析结果。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from app.purposes import Purpose

# 与 model_configs 表的列宽一致
BASE_URL_MAX_LENGTH = 512
MODEL_MAX_LENGTH = 128

ApiKeyStatus = Literal["set", "missing", "undecryptable"]


class Voice(BaseModel):
    """配音音色：speaker_id 是 TTS 接口里的音色 ID，label 是给老师看的名字。"""

    speaker_id: str
    label: str

    @field_validator("speaker_id", "label")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v


class ModelConfigView(BaseModel):
    """管理后台看到的一项配置。API key 只给状态和掩码，不给明文和密文。"""

    purpose: Purpose
    label: str
    required: bool
    base_url: str
    model: str
    enabled: bool
    api_key_status: ApiKeyStatus
    api_key_masked: str | None
    voices: list[Voice]
    last_test_ok: bool | None
    last_test_message: str | None
    last_tested_at: datetime | None


class ModelConfigUpdate(BaseModel):
    """修改一项配置。api_key 为 None / 空字符串时保留原来的 key；clear_api_key=True 时清空。"""

    base_url: str
    model: str
    enabled: bool
    # 不加长度等约束：校验失败时 FastAPI 会把原值写进 422 响应
    api_key: str | None = None
    clear_api_key: bool = False
    # 只有 tts 用；None 表示保留原来的音色
    voices: list[Voice] | None = None

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v:
            return ""
        lower = v.lower()
        scheme = next((s for s in ("http://", "https://") if lower.startswith(s)), None)
        if scheme is None or len(v) == len(scheme):
            raise ValueError("接口地址必须以 http:// 或 https:// 开头")
        if len(v) > BASE_URL_MAX_LENGTH:
            raise ValueError(f"接口地址不能超过 {BASE_URL_MAX_LENGTH} 个字符")
        return v

    @field_validator("model")
    @classmethod
    def _check_model(cls, v: str) -> str:
        v = v.strip()
        if len(v) > MODEL_MAX_LENGTH:
            raise ValueError(f"模型名称不能超过 {MODEL_MAX_LENGTH} 个字符")
        return v

    @field_validator("api_key")
    @classmethod
    def _blank_key_is_none(cls, v: str | None) -> str | None:
        # 复制粘贴常带首尾空白；去掉后为空就当作没填
        if v is None:
            return None
        return v.strip() or None


@dataclass
class ResolvedConfig:
    """业务代码调用模型接口时用的配置；api_key 是解密后的明文，不要记日志或返回给前端。"""

    purpose: Purpose
    base_url: str
    api_key: str = field(repr=False)
    model: str
    extra: dict[str, Any]
