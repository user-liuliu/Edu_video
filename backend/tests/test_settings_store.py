import pytest
from pydantic import ValidationError

from app.settings_store import (
    DEFAULT_FORM_FIELDS,
    FormFieldsConfig,
    GenerationParams,
    get_form_fields,
    get_generation_params,
    get_registration,
    put_form_fields,
)


def _fields_dump() -> list[dict]:
    """默认页面配置的可修改副本（普通 dict），用来构造各种非法配置。"""
    return DEFAULT_FORM_FIELDS.model_dump(mode="json")["fields"]


def _field(fields: list[dict], key: str) -> dict:
    return next(f for f in fields if f["key"] == key)


async def test_defaults_when_absent(db):
    f = {x.key: x for x in (await get_form_fields(db)).fields}
    assert f["subject"].default == "数学" and f["grade"].default == "初三"
    assert f["textbook_edition"].default == "人教版"
    assert f["textbook_edition"].default_by_subject == {
        "语文": "统编版",
        "历史": "统编版",
        "道德与法治": "统编版",
    }
    assert (await get_generation_params(db)).illustrations_per_minute == 4
    assert (await get_registration(db)).open is True


async def test_put_then_get_roundtrip(db):
    cfg = await get_form_fields(db)
    fields = cfg.model_dump(mode="json")["fields"]
    _field(fields, "aspect_ratio")["visible"] = False
    saved = await put_form_fields(db, FormFieldsConfig.model_validate({"fields": fields}))
    assert {x.key: x for x in saved.fields}["aspect_ratio"].visible is False

    again = {x.key: x for x in (await get_form_fields(db)).fields}
    assert again["aspect_ratio"].visible is False
    assert again["subject"].visible is True


def test_prompt_cannot_be_hidden():
    fields = _fields_dump()
    _field(fields, "prompt")["visible"] = False
    with pytest.raises(ValidationError):
        FormFieldsConfig.model_validate({"fields": fields})


def test_default_must_be_in_options():
    fields = _fields_dump()
    subject = _field(fields, "subject")
    subject["options"] = [o for o in subject["options"] if o["value"] != "数学"]
    assert subject["default"] == "数学"
    with pytest.raises(ValidationError) as exc:
        FormFieldsConfig.model_validate({"fields": fields})
    assert "默认值必须在可选值中" in str(exc.value)


def test_default_by_subject_must_reference_options():
    fields = _fields_dump()
    edition = _field(fields, "textbook_edition")
    edition["options"] = [o for o in edition["options"] if o["value"] != "统编版"]
    with pytest.raises(ValidationError) as exc:
        FormFieldsConfig.model_validate({"fields": fields})
    assert "默认值必须在可选值中" in str(exc.value)


def test_visuals_max_ge_min():
    with pytest.raises(ValidationError):
        GenerationParams(segment_visuals_min=5, segment_visuals_max=4)
