from cryptography.fernet import Fernet
from conftest import login, put

from app.model_configs import (
    DEFAULTS,
    ModelConfigUpdate,
    Voice,
    list_configs,
    list_voices,
    record_test,
    resolve,
    system_available,
    update_config,
)
from app.models import ModelConfigRow
from app.purposes import REQUIRED_PURPOSES, Purpose
from app.security import SecretBox

URL = "/api/admin/model-configs"
VOICES = [{"speaker_id": "zh_female_1", "label": "女声 1"}]


def _code(r) -> str:
    return r.json()["detail"]["code"]


def _full(purpose: str, **overrides) -> dict:
    """一套能通过“启用”校验的完整配置；tts 自动带上音色。"""
    body = {
        "base_url": f"https://{purpose}.example.com/v1",
        "model": f"{purpose}-model",
        "enabled": True,
        "api_key": f"sk-{purpose}-key1",
    }
    if purpose == "tts":
        body["voices"] = VOICES
    body.update(overrides)
    return body


async def _items(client) -> dict[str, dict]:
    r = await client.get(URL)
    assert r.status_code == 200, r.text
    return {i["purpose"]: i for i in r.json()}


async def _configure_required(client) -> None:
    for p in REQUIRED_PURPOSES:
        await put(client, p.value, **_full(p.value))


async def _configure_required_direct(db, box) -> None:
    for p in REQUIRED_PURPOSES:
        await update_config(db, box, p, ModelConfigUpdate(**_full(p.value)))


async def test_list_defaults_six_active_purposes(admin_client):
    items = (await admin_client.get("/api/admin/model-configs")).json()
    assert [i["purpose"] for i in items] == ["outline_llm","review_llm","vision_llm","embedding","tts","web_search"]
    tts = items[4]; assert tts["base_url"] == "https://openspeech.bytedance.com" and tts["model"] == "seed-audio-1.0"


async def test_list_defaults_details(admin_client, db):
    items = await _items(admin_client)
    assert items["embedding"]["model"] == "qwen3.7-text-embedding-flash"
    assert "image_gen" not in items
    assert items["outline_llm"]["label"] == "写大纲/讲稿"
    for p, item in items.items():
        assert item["required"] is (Purpose(p) in REQUIRED_PURPOSES)
        assert item["enabled"] is False
        assert item["api_key_status"] == "missing" and item["api_key_masked"] is None
        assert item["voices"] == [] and item["last_test_ok"] is None
        assert (item["base_url"], item["model"]) == DEFAULTS[Purpose(p)]
    # 只读不写：列表接口不会往库里插默认行
    assert await db.get(ModelConfigRow, "tts") is None


async def test_key_encrypted_and_masked(admin_client, db):
    await put(admin_client, "outline_llm", base_url="https://r.example.com/v1/", model="m", enabled=True, api_key="sk-secret-9f2a")
    row = await db.get(ModelConfigRow, "outline_llm")
    assert "sk-secret" not in row.api_key_encrypted and row.base_url == "https://r.example.com/v1"
    body = (await admin_client.get("/api/admin/model-configs")).text
    assert "sk-secret" not in body and '"api_key_masked":"****9f2a"' in body.replace(" ", "")


async def test_put_response_never_contains_key(admin_client, db):
    r = await admin_client.put(f"{URL}/outline_llm", json=_full("outline_llm", api_key="sk-topsecret-abcd"))
    assert r.status_code == 200
    row = await db.get(ModelConfigRow, "outline_llm")
    assert "topsecret" not in r.text and row.api_key_encrypted not in r.text
    assert r.json()["api_key_status"] == "set" and r.json()["api_key_masked"] == "****abcd"


async def test_omitted_key_is_kept(admin_client):
    await put(admin_client, "outline_llm", **_full("outline_llm", api_key="sk-keep-7777"))
    # 不带 api_key，也试一下空字符串和纯空白：都表示保留原值
    for extra in ({}, {"api_key": None}, {"api_key": ""}, {"api_key": "   "}):
        body = {"base_url": "https://outline_llm.example.com/v1", "model": "m2", "enabled": True, **extra}
        item = await put(admin_client, "outline_llm", **body)
        assert item["api_key_status"] == "set" and item["api_key_masked"] == "****7777", extra
    item = (await _items(admin_client))["outline_llm"]
    assert item["api_key_status"] == "set" and item["api_key_masked"] == "****7777"
    assert item["model"] == "m2"


async def test_clear_key(admin_client, db):
    await put(admin_client, "review_llm", **_full("review_llm"))
    # 启用状态下清空 key 不允许
    r = await admin_client.put(f"{URL}/review_llm", json=_full("review_llm", api_key=None, clear_api_key=True))
    assert r.status_code == 422 and _code(r) == "config_incomplete"

    item = await put(admin_client, "review_llm", **_full("review_llm", api_key=None, enabled=False, clear_api_key=True))
    assert item["api_key_status"] == "missing" and item["api_key_masked"] is None
    assert (await _items(admin_client))["review_llm"]["api_key_status"] == "missing"
    row = await db.get(ModelConfigRow, "review_llm")
    assert row.api_key_encrypted is None and row.enabled is False


async def test_enable_requires_key_and_model(admin_client, db):
    cases = [
        _full("outline_llm", api_key=None),
        _full("outline_llm", model=""),
        _full("outline_llm", model="   "),
        _full("outline_llm", base_url=""),
    ]
    for body in cases:
        r = await admin_client.put(f"{URL}/outline_llm", json=body)
        assert r.status_code == 422 and _code(r) == "config_incomplete", body
        assert r.json()["detail"]["message"]
    # 失败的请求什么都没存
    assert await db.get(ModelConfigRow, "outline_llm") is None

    # 不启用时可以先存半成品
    item = await put(admin_client, "outline_llm", base_url="", model="", enabled=False, api_key="sk-half-1234")
    assert item["api_key_status"] == "set" and item["enabled"] is False
    # 之后补齐地址和模型即可启用，用原来的 key
    item = await put(admin_client, "outline_llm", base_url="https://x.example.com", model="m", enabled=True)
    assert item["enabled"] is True and item["api_key_masked"] == "****1234"

    # web_search 不要求 model，但仍要求 key 和地址
    item = await put(admin_client, "web_search", **_full("web_search", model=""))
    assert item["enabled"] is True
    r = await admin_client.put(f"{URL}/web_search", json=_full("web_search", model="", base_url=""))
    assert r.status_code == 422 and _code(r) == "config_incomplete"


async def test_base_url_validation(admin_client):
    for bad in ("ftp://x.example.com", "x.example.com", "https://", "http:/x"):
        r = await admin_client.put(f"{URL}/outline_llm", json=_full("outline_llm", base_url=bad))
        assert r.status_code == 422, bad
    item = await put(admin_client, "outline_llm", **_full("outline_llm", base_url="  https://a.example.com/v1//  "))
    assert item["base_url"] == "https://a.example.com/v1"


async def test_invalid_purpose_is_422(admin_client):
    r = await admin_client.put(f"{URL}/nope", json=_full("outline_llm"))
    assert r.status_code == 422


async def test_tts_voices_validation(admin_client, db):
    bad_voice_lists = [
        [],
        None,  # 启用 tts 但从来没存过音色
        [{"speaker_id": "a", "label": "A"}, {"speaker_id": "a", "label": "B"}],
        [{"speaker_id": "a", "label": "A"}, {"speaker_id": " a ", "label": "B"}],
    ]
    for voices in bad_voice_lists:
        r = await admin_client.put(f"{URL}/tts", json=_full("tts", voices=voices))
        assert r.status_code == 422 and _code(r) == "invalid_voices", voices
    # speaker_id / label 为空白时是普通的请求体校验错误
    for v in ({"speaker_id": " ", "label": "A"}, {"speaker_id": "a", "label": ""}):
        r = await admin_client.put(f"{URL}/tts", json=_full("tts", voices=[v]))
        assert r.status_code == 422, v
    assert await db.get(ModelConfigRow, "tts") is None

    item = await put(admin_client, "tts", **_full("tts", voices=[{"speaker_id": " s1 ", "label": " 女声 "}, {"speaker_id": "s2", "label": "男声"}]))
    assert item["voices"] == [{"speaker_id": "s1", "label": "女声"}, {"speaker_id": "s2", "label": "男声"}]
    # 不带 voices 时保留原来的音色
    item = await put(admin_client, "tts", **_full("tts", voices=None))
    assert [v["speaker_id"] for v in item["voices"]] == ["s1", "s2"]
    assert [v.speaker_id for v in await list_voices(db)] == ["s1", "s2"]
    # 已存过音色后再传空列表启用，仍然拒绝
    r = await admin_client.put(f"{URL}/tts", json=_full("tts", voices=[]))
    assert r.status_code == 422 and _code(r) == "invalid_voices"

    # 其他用途忽略 voices
    item = await put(admin_client, "outline_llm", **_full("outline_llm", voices=VOICES))
    assert item["voices"] == []
    row = await db.get(ModelConfigRow, "outline_llm")
    assert "voices" not in row.extra


async def test_resolve(db, box):
    assert await resolve(db, box, Purpose.tts) is None
    await update_config(db, box, Purpose.tts, ModelConfigUpdate(**_full("tts", api_key="sk-plain-0001")))
    cfg = await resolve(db, box, Purpose.tts)
    assert cfg is not None and cfg.purpose == Purpose.tts
    assert cfg.api_key == "sk-plain-0001" and cfg.model == "tts-model"
    assert cfg.base_url == "https://tts.example.com/v1"
    assert cfg.extra == {"voices": VOICES}

    # 没启用：默认返回 None；require_enabled=False 时照样返回
    await update_config(db, box, Purpose.outline_llm, ModelConfigUpdate(**_full("outline_llm", enabled=False)))
    assert await resolve(db, box, Purpose.outline_llm) is None
    assert (await resolve(db, box, Purpose.outline_llm, require_enabled=False)).api_key == "sk-outline_llm-key1"
    # 没 key / 没 model 时 require_enabled=False 也返回 None
    await update_config(db, box, Purpose.review_llm, ModelConfigUpdate(base_url="https://r.example.com", model="m", enabled=False))
    assert await resolve(db, box, Purpose.review_llm, require_enabled=False) is None
    await update_config(db, box, Purpose.vision_llm, ModelConfigUpdate(base_url="https://v.example.com", model="", enabled=False, api_key="k1234"))
    assert await resolve(db, box, Purpose.vision_llm, require_enabled=False) is None
    # web_search 不检查 model
    await update_config(db, box, Purpose.web_search, ModelConfigUpdate(**_full("web_search", model="")))
    assert (await resolve(db, box, Purpose.web_search)).model == ""


async def test_undecryptable_key(app, db, admin_client):
    # 先用当前的 box 存一个 key，再把 app.state.secret_box 换成用另一个 Fernet key 创建的 SecretBox
    await _configure_required(admin_client)
    assert await system_available(db, app.state.secret_box) is True
    app.state.secret_box = SecretBox(Fernet.generate_key().decode())

    r = await admin_client.get(URL)
    assert r.status_code == 200
    item = {i["purpose"]: i for i in r.json()}["outline_llm"]
    assert item["api_key_status"] == "undecryptable" and item["api_key_masked"] is None
    assert await system_available(db, app.state.secret_box) is False
    assert await resolve(db, app.state.secret_box, Purpose.outline_llm) is None

    # 解不开的 key 算作没有 key：不填新 key 就不能保持启用
    r = await admin_client.put(f"{URL}/outline_llm", json=_full("outline_llm", api_key=None))
    assert r.status_code == 422 and _code(r) == "config_incomplete"
    # 不启用时可以保存，状态仍是 undecryptable
    item = await put(admin_client, "outline_llm", **_full("outline_llm", api_key=None, enabled=False))
    assert item["api_key_status"] == "undecryptable"
    # 填一个新 key 就恢复正常
    item = await put(admin_client, "outline_llm", **_full("outline_llm", api_key="sk-new-5555"))
    assert item["api_key_status"] == "set" and item["api_key_masked"] == "****5555"


async def test_system_available(db, box):
    assert await system_available(db, box) is False
    await _configure_required_direct(db, box)
    # 4 个必需项都配好，不配 web_search 和 embedding 也可用
    assert await system_available(db, box) is True
    for p in (Purpose.web_search, Purpose.embedding):
        assert p not in REQUIRED_PURPOSES
        assert await resolve(db, box, p) is None

    # 任意一个必需项最近一次测试失败就不可用；测试通过后恢复
    for p in REQUIRED_PURPOSES:
        await record_test(db, p, False, "连接超时")
        assert await system_available(db, box) is False, p
        await record_test(db, p, True, "ok")
        assert await system_available(db, box) is True, p

    # 可选项测试失败不影响
    await record_test(db, Purpose.web_search, False, "x")
    assert await system_available(db, box) is True

    # 必需项被停用也不可用
    await update_config(db, box, Purpose.tts, ModelConfigUpdate(**_full("tts", enabled=False)))
    assert await system_available(db, box) is False


async def test_record_test(db, box):
    await record_test(db, Purpose.embedding, False, "错" * 600)
    items = {i.purpose: i for i in await list_configs(db, box)}
    emb = items[Purpose.embedding]
    assert emb.last_test_ok is False and len(emb.last_test_message) == 500
    assert emb.last_tested_at is not None
    # 新建的行用默认值
    assert (emb.base_url, emb.model) == DEFAULTS[Purpose.embedding]


async def test_changing_base_url_resets_test_status(admin_client, db):
    for change in ({"base_url": "https://other.example.com"}, {"model": "other-model"}, {"api_key": "sk-other-2222"}, {"api_key": None, "enabled": False, "clear_api_key": True}):
        await put(admin_client, "outline_llm", **_full("outline_llm"))
        await record_test(db, Purpose.outline_llm, False, "401 Unauthorized")
        item = (await _items(admin_client))["outline_llm"]
        assert item["last_test_ok"] is False and item["last_test_message"] == "401 Unauthorized"
        assert item["last_tested_at"] is not None

        # 地址、模型、key 都没变（只改启用状态）：测试结果保留
        item = await put(admin_client, "outline_llm", **_full("outline_llm", api_key=None, enabled=False))
        assert item["last_test_ok"] is False, change

        item = await put(admin_client, "outline_llm", **_full("outline_llm", **{"api_key": None, **change}))
        assert item["last_test_ok"] is None and item["last_test_message"] is None, change
        assert item["last_tested_at"] is None, change
        assert (await _items(admin_client))["outline_llm"]["last_test_ok"] is None, change


async def test_model_config_admin_only(client, make_user):
    await make_user("t1")
    r = await client.get(URL)
    assert r.status_code == 401 and _code(r) == "not_authenticated"
    await login(client, "t1", "pass1234")
    r = await client.get(URL)
    assert r.status_code == 403 and _code(r) == "forbidden"
    r = await client.put(f"{URL}/outline_llm", json=_full("outline_llm"))
    assert r.status_code == 403 and _code(r) == "forbidden"


def test_voice_model_strips():
    assert Voice(speaker_id=" a ", label=" b ").model_dump() == {"speaker_id": "a", "label": "b"}


async def test_422_does_not_echo_api_key(admin_client):
    r = await admin_client.put(f"{URL}/outline_llm", json={"base_url": "https://a.example.com", "api_key": "sk-LEAK-1234"})
    assert r.status_code == 422
    assert "sk-LEAK-1234" not in r.text
    errors = r.json()["detail"]
    assert isinstance(errors, list) and errors
    assert all(set(e) == {"type", "loc", "msg"} for e in errors)


async def test_non_ascii_api_key_rejected(admin_client, db):
    """key 里混进全角逗号等非 ASCII 字符：422，提示里不带 key。"""
    key = "sk-abc，def"
    r = await admin_client.put(f"{URL}/outline_llm", json=_full("outline_llm", api_key=key))
    assert r.status_code == 422
    assert key not in r.text and "abc" not in r.text
    assert "Key 只能包含英文字母、数字和符号" in r.json()["detail"][0]["msg"]
    assert await db.get(ModelConfigRow, "outline_llm") is None


def test_update_repr_hides_api_key():
    upd = ModelConfigUpdate(base_url="", model="", enabled=False, api_key="sk-hidden-5678")
    assert "sk-hidden-5678" not in repr(upd)


async def test_legacy_image_config_is_preserved_but_not_active(db, box, admin_client, teacher_client):
    for p in (Purpose.outline_llm, Purpose.review_llm, Purpose.vision_llm, Purpose.tts):
        await update_config(db, box, p, ModelConfigUpdate(**_full(p.value)))
    legacy = ModelConfigRow(purpose='image_gen', base_url='https://old.invalid',
        model='old-image', enabled=True, api_key_encrypted='legacy-ciphertext',
        extra={}, last_test_ok=False)
    db.add(legacy)
    await db.commit()
    assert 'image_gen' not in await _items(admin_client)
    assert await system_available(db, box) is True
    assert (await teacher_client.get('/api/config/form')).json()['system_available'] is True
    await db.refresh(legacy)
    assert legacy.api_key_encrypted == 'legacy-ciphertext'
    assert legacy.enabled is True


async def test_retired_image_configuration_endpoints_reject_requests(admin_client, db, respx_mock):
    response = await admin_client.put(f'{URL}/image_gen', json=_full('image_gen'))
    assert response.status_code == 422
    response = await admin_client.post(f'{URL}/image_gen/test')
    assert response.status_code == 422
    assert await db.get(ModelConfigRow, 'image_gen') is None
    assert len(respx_mock.calls) == 0
