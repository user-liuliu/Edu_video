"""系统设置存储：注册开关、新建视频页面配置、生成参数。"""

from .defaults import DEFAULT_FORM_FIELDS
from .schemas import (
    FieldConfig,
    FieldKey,
    FieldOption,
    FormFieldsConfig,
    GenerationParams,
    RegistrationSettings,
)
from .service import (
    get_form_fields,
    get_generation_params,
    get_registration,
    put_form_fields,
    put_generation_params,
    put_registration,
)

__all__ = [
    "DEFAULT_FORM_FIELDS",
    "FieldConfig",
    "FieldKey",
    "FieldOption",
    "FormFieldsConfig",
    "GenerationParams",
    "RegistrationSettings",
    "get_form_fields",
    "get_generation_params",
    "get_registration",
    "put_form_fields",
    "put_generation_params",
    "put_registration",
]
