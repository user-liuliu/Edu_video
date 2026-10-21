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


def test_retired_explanation_style_is_not_a_form_field():
    assert 'style' not in {field.key for field in DEFAULT_FORM_FIELDS.fields}


def test_legacy_style_config_is_ignored_without_mutating_input():
    fields = [f for f in _fields_dump() if f['key'] != 'style']
    fields.append({'key': 'style', 'default': 'removed-custom-style'})
    config = FormFieldsConfig.model_validate({'fields': fields})
    assert 'style' not in {field.key for field in config.fields}
    assert fields[-1] == {'key': 'style', 'default': 'removed-custom-style'}


def test_retired_style_submission_is_ignored_and_voice_is_preserved():
    from app.model_configs.schemas import Voice
    from app.settings_store.form_values import resolve_form_values
    values = resolve_form_values(DEFAULT_FORM_FIELDS, {'style': 'old-custom-style', 'voice': 'v1'},
        voices=[Voice(speaker_id='v1', label='温和女声')], search_ready=False)
    assert 'style' not in values
    assert values['voice'] == 'v1'


async def test_legacy_form_config_is_retired_in_admin_public_and_saved_settings(db, admin_client, teacher_client):
    from app.models import SystemSetting
    fields = [f for f in _fields_dump() if f['key'] != 'style']
    fields.append({'key': 'style', 'default': 'old-custom-style'})
    row = SystemSetting(key='form_fields', value={'fields': fields})
    db.add(row)
    await db.commit()
    for path in ('/api/admin/settings/form-fields', '/api/config/form'):
        client = admin_client if '/admin/' in path else teacher_client
        response = await client.get(path)
        assert response.status_code == 200, response.text
        assert 'style' not in {f['key'] for f in response.json()['fields']}
    saved = await admin_client.put('/api/admin/settings/form-fields', json={'fields': fields})
    assert saved.status_code == 200, saved.text
    await db.refresh(row)
    assert 'style' not in {f['key'] for f in row.value['fields']}
    assert _field(row.value['fields'], 'subject')['default'] == '数学'


async def test_defaults_when_absent(db):
    f = {x.key: x for x in (await get_form_fields(db)).fields}
    assert f["subject"].default == "数学" and f["grade"].default == "初三"
    assert f["textbook_edition"].default == "人教版"
    assert f["textbook_edition"].default_by_subject == {
        "语文": "统编版",
        "历史": "统编版",
        "道德与法治": "统编版",
    }
    assert (await get_generation_params(db)).model_dump() == {
        'max_concurrent_jobs': 2, 'max_retries': 2,
        'duration_tolerance_pct': 15, 'long_term_memory_enabled': True,
    }
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


async def test_legacy_generation_settings_ignore_retired_counts(db, admin_client):
    from app.models import SystemSetting
    row = SystemSetting(key='generation_params', value={
        'segment_visuals_min': 8, 'segment_visuals_max': 2,
        'illustrations_per_minute': 4, 'max_concurrent_jobs': 3,
        'max_retries': 1, 'duration_tolerance_pct': 20, 'long_term_memory_enabled': False,
    })
    db.add(row)
    await db.commit()
    expected = {'max_concurrent_jobs': 3, 'max_retries': 1,
        'duration_tolerance_pct': 20, 'long_term_memory_enabled': False}
    endpoint = '/api/admin/settings/generation-params'
    response = await admin_client.get(endpoint)
    assert response.status_code == 200
    assert response.json() == expected
    response = await admin_client.put(endpoint, json={**row.value, 'max_concurrent_jobs': 4})
    assert response.status_code == 200
    assert response.json() == {**expected, 'max_concurrent_jobs': 4}
    await db.refresh(row)
    assert row.value == {**expected, 'max_concurrent_jobs': 4}


@pytest.mark.parametrize('values', [
    {'max_concurrent_jobs': 0}, {'max_concurrent_jobs': 21},
    {'max_retries': -1}, {'max_retries': 6},
    {'duration_tolerance_pct': 4}, {'duration_tolerance_pct': 51},
])
def test_retained_generation_limits_are_validated(values):
    with pytest.raises(ValidationError):
        GenerationParams(**values)
