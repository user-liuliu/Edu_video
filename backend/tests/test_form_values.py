import pytest
from fastapi import HTTPException

from app.settings_store.defaults import DEFAULT_FORM_FIELDS
from app.settings_store.form_values import resolve_form_values


def test_hidden_values_cannot_be_overridden_and_subject_default():
    config = DEFAULT_FORM_FIELDS.model_copy(deep=True)
    next(f for f in config.fields if f.key == 'grade').visible = False
    values = resolve_form_values(config, {'subject': '语文', 'grade': '高三', 'web_search': True}, voices=[], search_ready=False)
    assert values['grade'] == '初三'
    assert values['textbook_edition'] == '统编版'
    assert values['web_search'] is False


@pytest.mark.parametrize('submitted', [{'duration':'custom', 'custom_duration_minutes':0}, {'grade':'不存在'}, {'web_search':'false'}, {'textbook_edition':'统编版', 'subject':'数学'}])
def test_invalid_form_values_rejected(submitted):
    with pytest.raises(HTTPException) as error:
        resolve_form_values(DEFAULT_FORM_FIELDS, submitted, voices=[], search_ready=True)
    assert error.value.status_code == 422


def test_custom_duration():
    values = resolve_form_values(DEFAULT_FORM_FIELDS, {'duration':'custom', 'custom_duration_minutes':7.5}, voices=[], search_ready=False)
    assert values['duration_seconds'] == 450
