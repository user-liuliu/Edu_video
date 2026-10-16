from conftest import login, put

from app.purposes import REQUIRED_PURPOSES

FORM_URL = "/api/admin/settings/form-fields"
PARAMS_URL = "/api/admin/settings/generation-params"
PUBLIC_URL = "/api/config/form"
TWO_VOICES = [
    {"speaker_id": "zh_female_1", "label": "女声 1"},
    {"speaker_id": "zh_male_2", "label": "男声 2"},
]


def _full(purpose: str, **overrides) -> dict:
    """一套能通过“启用”校验的完整配置；tts 自动带上音色。"""
    body = {
        "base_url": f"https://{purpose}.example.com/v1",
        "model": f"{purpose}-model",
        "enabled": True,
        "api_key": f"sk-{purpose}-key1",
    }
    if purpose == "tts":
        body["voices"] = TWO_VOICES
    body.update(overrides)
    return body


async def _form(admin_client) -> dict:
    r = await admin_client.get(FORM_URL)
    assert r.status_code == 200, r.text
    return r.json()


def _field(cfg: dict, key: str) -> dict:
    return next(f for f in cfg["fields"] if f["key"] == key)


async def _hide(admin_client, key: str) -> None:
    cfg = await _form(admin_client)
    _field(cfg, key)["visible"] = False
    r = await admin_client.put(FORM_URL, json=cfg)
    assert r.status_code == 200, r.text


async def _public(teacher_client) -> dict:
    r = await teacher_client.get(PUBLIC_URL)
    assert r.status_code == 200, r.text
    return r.json()


def _public_field(cfg: dict, key: str) -> dict | None:
    return next((f for f in cfg["fields"] if f["key"] == key), None)


async def test_admin_form_fields_roundtrip_and_validation(admin_client):
    cfg = await _form(admin_client)
    assert len(cfg["fields"]) == 10
    _field(cfg, "aspect_ratio")["visible"] = False
    r = await admin_client.put(FORM_URL, json=cfg)
    assert r.status_code == 200, r.text
    assert _field(r.json(), "aspect_ratio")["visible"] is False
    assert _field(await _form(admin_client), "aspect_ratio")["visible"] is False

    # 删掉科目里的 "数学"（也是科目的默认值）：校验失败
    subject = _field(cfg, "subject")
    subject["options"] = [o for o in subject["options"] if o["value"] != "数学"]
    r = await admin_client.put(FORM_URL, json=cfg)
    assert r.status_code == 422
    assert "默认值必须在可选值中" in r.text
    # 失败的请求没有改动已保存的配置
    saved = _field(await _form(admin_client), "subject")
    assert "数学" in [o["value"] for o in saved["options"]]


async def test_public_hides_invisible_fields(teacher_client, admin_client):
    await _hide(admin_client, "aspect_ratio")
    keys = [f["key"] for f in (await teacher_client.get("/api/config/form")).json()["fields"]]
    assert "aspect_ratio" not in keys and "prompt" in keys


async def test_public_field_shape(teacher_client):
    cfg = await _public(teacher_client)
    edition = _public_field(cfg, "textbook_edition")
    assert set(edition) == {"key", "label", "default", "options", "default_by_subject"}
    assert edition["label"] == "教材版本" and edition["default"] == "人教版"
    assert edition["default_by_subject"]["语文"] == "统编版"
    tongbian = next(o for o in edition["options"] if o["value"] == "统编版")
    assert tongbian == {"value": "统编版", "label": "统编版", "subjects": ["语文", "历史", "道德与法治"]}


async def test_public_voice_options_from_tts(teacher_client, admin_client):
    # tts 没配好时不返回 voice 字段
    assert _public_field(await _public(teacher_client), "voice") is None

    await put(admin_client, "tts", **_full("tts"))
    voice = _public_field(await _public(teacher_client), "voice")
    assert voice["options"] == [
        {"value": "zh_female_1", "label": "女声 1", "subjects": None},
        {"value": "zh_male_2", "label": "男声 2", "subjects": None},
    ]
    assert voice["default"] == "zh_female_1"

    # tts 停用后音色还在库里，但不再返回 voice 字段
    await put(admin_client, "tts", **_full("tts", enabled=False))
    assert _public_field(await _public(teacher_client), "voice") is None

    # 管理员隐藏 voice 后，即使 tts 可用也不返回
    await put(admin_client, "tts", **_full("tts"))
    await _hide(admin_client, "voice")
    assert _public_field(await _public(teacher_client), "voice") is None


async def test_public_omits_web_search_when_unconfigured(teacher_client, admin_client):
    assert _public_field(await _public(teacher_client), "web_search") is None
    # 填了但没启用：仍不返回
    await put(admin_client, "web_search", **_full("web_search", model="", enabled=False))
    assert _public_field(await _public(teacher_client), "web_search") is None

    await put(admin_client, "web_search", **_full("web_search", model=""))
    web = _public_field(await _public(teacher_client), "web_search")
    assert web is not None and web["default"] is True


async def test_public_reports_system_unavailable(teacher_client, admin_client):
    assert (await _public(teacher_client))["system_available"] is False
    for p in REQUIRED_PURPOSES:
        await put(admin_client, p.value, **_full(p.value))
    assert (await _public(teacher_client))["system_available"] is True


async def test_public_never_leaks_model_info(teacher_client, admin_client):
    await put(
        admin_client, "outline_llm",
        base_url="https://r.example.com/v1", model="m", enabled=True, api_key="sk-secret-9f2a",
    )
    await put(admin_client, "tts", **_full("tts"))
    await put(admin_client, "web_search", **_full("web_search", model=""))
    r = await teacher_client.get(PUBLIC_URL)
    assert r.status_code == 200
    for needle in ("https://r.example.com/v1", "sk-secret", "****9f2a", "generation",
                   "tts.example.com", "sk-tts", "tts-model", "web_search.example.com"):
        assert needle not in r.text, needle
    assert set(r.json()) == {"system_available", "fields"}


async def test_public_requires_active(client, make_user):
    # 没登录
    r = await client.get(PUBLIC_URL)
    assert r.status_code == 401
    await make_user("p1", status="pending")
    await login(client, "p1", "pass1234")
    r = await client.get(PUBLIC_URL)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_pending"


async def test_generation_params_admin_only_and_validation(teacher_client, admin_client):
    # 老师不能读写页面配置和生成参数
    for url in (PARAMS_URL, FORM_URL):
        r = await teacher_client.get(url)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    r = await teacher_client.put(PARAMS_URL, json={"max_concurrent_jobs": 3})
    assert r.status_code == 403
    r = await teacher_client.put(FORM_URL, json=await _form(admin_client))
    assert r.status_code == 403

    r = await admin_client.get(PARAMS_URL)
    assert r.status_code == 200 and r.json()["max_concurrent_jobs"] == 2
    params = {**r.json(), "max_concurrent_jobs": 0}
    r = await admin_client.put(PARAMS_URL, json=params)
    assert r.status_code == 422
    assert (await admin_client.get(PARAMS_URL)).json()["max_concurrent_jobs"] == 2

    params["max_concurrent_jobs"] = 5
    r = await admin_client.put(PARAMS_URL, json=params)
    assert r.status_code == 200 and r.json()["max_concurrent_jobs"] == 5
    assert (await admin_client.get(PARAMS_URL)).json()["max_concurrent_jobs"] == 5
