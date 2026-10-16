"""系统设置的数据结构：新建视频页面配置、生成参数、注册开关。"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class FieldKey(StrEnum):
    """新建视频页面上的表单项。"""

    prompt = "prompt"
    materials = "materials"
    subject = "subject"
    grade = "grade"
    textbook_edition = "textbook_edition"
    duration = "duration"
    aspect_ratio = "aspect_ratio"
    style = "style"
    voice = "voice"
    web_search = "web_search"


# 必须带可选值的表单项：options 不能为空、value 不能重复、default 必须是其中之一
OPTION_FIELDS: tuple[FieldKey, ...] = (
    FieldKey.subject,
    FieldKey.grade,
    FieldKey.textbook_edition,
    FieldKey.duration,
    FieldKey.aspect_ratio,
    FieldKey.style,
)

DEFAULT_NOT_IN_OPTIONS = "默认值必须在可选值中"


class FieldOption(BaseModel):
    value: str
    label: str
    # 只有教材版本用：这个版本适用于哪些科目（subject 的 option value），None 表示适用于所有科目
    subjects: list[str] | None = None


class FieldConfig(BaseModel):
    key: FieldKey
    label: str
    visible: bool
    default: str | bool | None
    options: list[FieldOption] = Field(default_factory=list)
    # 按科目指定默认值：科目（subject 的 option value）-> 本项的 option value
    default_by_subject: dict[str, str] = Field(default_factory=dict)


class FormFieldsConfig(BaseModel):
    fields: list[FieldConfig]

    @model_validator(mode="after")
    def _check(self) -> Self:
        by_key: dict[FieldKey, FieldConfig] = {}
        for f in self.fields:
            if f.key in by_key:
                raise ValueError(f"表单项 {f.key} 重复出现")
            by_key[f.key] = f
        missing = [k.value for k in FieldKey if k not in by_key]
        if missing:
            raise ValueError(f"缺少表单项：{', '.join(missing)}")

        if not by_key[FieldKey.prompt].visible:
            raise ValueError("“想讲什么”必须显示")

        values: dict[FieldKey, set[str]] = {}
        for key in OPTION_FIELDS:
            f = by_key[key]
            if not f.options:
                raise ValueError(f"表单项 {key} 的可选值不能为空")
            option_values = [o.value for o in f.options]
            if len(set(option_values)) != len(option_values):
                raise ValueError(f"表单项 {key} 的可选值不能重复")
            values[key] = set(option_values)
            # bool 默认值不可能匹配字符串 option，这里显式排除，免得 True/"True" 之类的混淆
            if not isinstance(f.default, str) or f.default not in values[key]:
                raise ValueError(
                    f"{DEFAULT_NOT_IN_OPTIONS}：{key} 的默认值 {f.default!r} 不在可选值里"
                )

        subjects = values[FieldKey.subject]
        for f in self.fields:
            for o in f.options:
                bad = [s for s in o.subjects or [] if s not in subjects]
                if bad:
                    raise ValueError(
                        f"{DEFAULT_NOT_IN_OPTIONS}：{f.key} 的选项 {o.value!r} "
                        f"适用的科目 {bad} 不在科目的可选值里"
                    )

        editions = values[FieldKey.textbook_edition]
        for f in self.fields:
            for subject, value in f.default_by_subject.items():
                if subject not in subjects:
                    raise ValueError(
                        f"{DEFAULT_NOT_IN_OPTIONS}：{f.key} 按科目默认值里的科目 "
                        f"{subject!r} 不在科目的可选值里"
                    )
                if value not in editions:
                    raise ValueError(
                        f"{DEFAULT_NOT_IN_OPTIONS}：{f.key} 按科目默认值里 {subject!r} 对应的 "
                        f"{value!r} 不在教材版本的可选值里"
                    )
        return self


class GenerationParams(BaseModel):
    segment_visuals_min: int = Field(3, ge=1, le=10)
    segment_visuals_max: int = Field(6, ge=1, le=12)
    illustrations_per_minute: int = Field(4, ge=0, le=20)
    max_concurrent_jobs: int = Field(2, ge=1, le=20)
    max_retries: int = Field(2, ge=0, le=5)
    duration_tolerance_pct: int = Field(15, ge=5, le=50)
    long_term_memory_enabled: bool = True

    @model_validator(mode="after")
    def _check_visuals(self) -> Self:
        if self.segment_visuals_max < self.segment_visuals_min:
            raise ValueError("每段画面数的上限不能小于下限")
        return self


class RegistrationSettings(BaseModel):
    open: bool = True
