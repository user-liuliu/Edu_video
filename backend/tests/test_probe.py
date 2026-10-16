import json

import httpx
from conftest import put

from app.model_configs.probe import join_url, redact

URL = "/api/admin/model-configs"
BASE = "https://r.example.com/v1"
TTS_BASE = "https://openspeech.bytedance.com"
VOICES = [
    {"speaker_id": "zh_female_1", "label": "女声 1"},
    {"speaker_id": "zh_male_2", "label": "男声 2"},
]


async def _test(client, purpose: str) -> httpx.Response:
    return await client.post(f"{URL}/{purpose}/test")


async def _items(client) -> dict[str, dict]:
    r = await client.get(URL)
    assert r.status_code == 200, r.text
    return {i["purpose"]: i for i in r.json()}


def _code(r) -> str:
    return r.json()["detail"]["code"]


def test_join_url():
    assert join_url("https://r.example.com/v1/", "/chat/completions") == "https://r.example.com/v1/chat/completions"
    assert join_url("https://r.example.com/v1", "chat/completions") == "https://r.example.com/v1/chat/completions"


def test_redact():
    assert redact("bad key sk-1 and sk-1", "sk-1") == "bad key **** and ****"
    assert redact("no secret here", "") == "no secret here"


async def test_llm_probe_ok_records(admin_client, respx_mock):
    route = respx_mock.post(f"{BASE}/chat/completions").respond(200, json={"choices": []})
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-secret-9f2a")
    r = await _test(admin_client, "outline_llm")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "message": "连接正常"}
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer sk-secret-9f2a"
    assert json.loads(req.content) == {"model": "m1", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    item = (await _items(admin_client))["outline_llm"]
    assert item["last_test_ok"] is True and item["last_test_message"] == "连接正常"
    assert item["last_tested_at"] is not None


async def test_llm_probe_http_error_redacts_key(admin_client, respx_mock):
    respx_mock.post(f"{BASE}/chat/completions").respond(401, text="invalid key sk-secret-9f2a")
    await put(admin_client, "review_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-secret-9f2a")
    r = await _test(admin_client, "review_llm")
    assert r.json()["ok"] is False and "sk-secret-9f2a" not in r.text and r.json()["message"].startswith("HTTP 401")
    assert r.json()["message"] == "HTTP 401：invalid key ****"
    item = (await _items(admin_client))["review_llm"]
    assert item["last_test_ok"] is False and "sk-secret-9f2a" not in item["last_test_message"]


async def test_http_error_body_truncated(admin_client, respx_mock):
    respx_mock.post(f"{BASE}/chat/completions").respond(500, text="x" * 300)
    await put(admin_client, "vision_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "vision_llm")
    assert r.json() == {"ok": False, "message": "HTTP 500：" + "x" * 200}


async def test_http_error_key_at_truncation_boundary(admin_client, respx_mock):
    # key 跨在第 200 个字符处：要先替换再截断，不能留下半截 key
    respx_mock.post(f"{BASE}/chat/completions").respond(400, text="x" * 195 + "sk-secret-9f2a" + "z" * 50)
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-secret-9f2a")
    r = await _test(admin_client, "outline_llm")
    assert r.json() == {"ok": False, "message": "HTTP 400：" + ("x" * 195 + "****" + "z" * 50)[:200]}
    assert "sk-se" not in r.text


async def test_timeout_message(admin_client, respx_mock):
    respx_mock.post(f"{BASE}/chat/completions").mock(side_effect=httpx.ConnectTimeout("timed out"))
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "outline_llm")
    assert r.status_code == 200
    assert r.json() == {"ok": False, "message": "连接超时"}
    assert (await _items(admin_client))["outline_llm"]["last_test_message"] == "连接超时"


async def test_connect_error_message(admin_client, respx_mock):
    respx_mock.post(f"{BASE}/chat/completions").mock(side_effect=httpx.ConnectError("refused"))
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "outline_llm")
    assert r.json() == {"ok": False, "message": "无法连接到 r.example.com"}


async def test_embedding_probe(admin_client, respx_mock):
    route = respx_mock.post(f"{BASE}/embeddings").respond(200, json={"data": []})
    await put(admin_client, "embedding", base_url=BASE, model="emb-1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "embedding")
    assert r.json() == {"ok": True, "message": "连接正常"}
    assert json.loads(route.calls.last.request.content) == {"model": "emb-1", "input": "ping"}


async def test_image_probe_model_found(admin_client, respx_mock):
    route = respx_mock.get(f"{BASE}/models").respond(200, json={"data": [{"id": "other"}, {"id": "img-1"}]})
    await put(admin_client, "image_gen", base_url=BASE, model="img-1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "image_gen")
    assert r.json() == {"ok": True, "message": "连接正常"}
    assert route.calls.last.request.headers["Authorization"] == "Bearer sk-k1"


async def test_image_probe_model_missing(admin_client, respx_mock):
    respx_mock.get(f"{BASE}/models").respond(200, json={"data": [{"id": "other"}]})
    await put(admin_client, "image_gen", base_url=BASE, model="img-1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "image_gen")
    assert r.json()["ok"] is False and "没有找到模型" in r.json()["message"]
    assert r.json()["message"] == "接口可用，但没有找到模型 img-1"
    assert (await _items(admin_client))["image_gen"]["last_test_ok"] is False


async def test_image_probe_no_data_list(admin_client, respx_mock):
    respx_mock.get(f"{BASE}/models").respond(200, json={"object": "list"})
    await put(admin_client, "image_gen", base_url=BASE, model="img-1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "image_gen")
    assert r.json() == {"ok": False, "message": "接口可用，但没有找到模型 img-1"}


async def test_tts_probe_uses_x_api_key_and_first_voice(admin_client, respx_mock):
    route = respx_mock.post(f"{TTS_BASE}/api/v3/tts/create").respond(200, json={"code": 20000000, "message": "ok"})
    await put(admin_client, "tts", base_url=TTS_BASE, model="seed-audio-1.0", enabled=False, api_key="tts-key-77", voices=VOICES)
    r = await _test(admin_client, "tts")
    assert r.json() == {"ok": True, "message": "连接正常"}
    assert len(respx_mock.calls) == 1
    req = respx_mock.calls.last.request
    assert req.headers["X-Api-Key"] == "tts-key-77"
    assert "Authorization" not in req.headers
    assert json.loads(req.content) == {"model": "seed-audio-1.0", "text_prompt": "测试", "speaker": "zh_female_1"}
    assert route.called


async def test_tts_probe_code_zero_or_absent_ok(admin_client, respx_mock):
    route = respx_mock.post(f"{TTS_BASE}/api/v3/tts/create")
    await put(admin_client, "tts", base_url=TTS_BASE, model="seed-audio-1.0", enabled=False, api_key="tts-key-77", voices=VOICES)
    for resp in (httpx.Response(200, json={"code": 0}), httpx.Response(200, json={"data": "x"}), httpx.Response(200, content=b"\x00audio")):
        route.mock(return_value=resp)
        assert (await _test(admin_client, "tts")).json() == {"ok": True, "message": "连接正常"}


async def test_tts_probe_error_code(admin_client, respx_mock):
    respx_mock.post(f"{TTS_BASE}/api/v3/tts/create").respond(
        200, json={"code": 45000001, "message": "bad speaker for tts-key-77 " + "y" * 300}
    )
    await put(admin_client, "tts", base_url=TTS_BASE, model="seed-audio-1.0", enabled=False, api_key="tts-key-77", voices=VOICES)
    r = await _test(admin_client, "tts")
    msg = r.json()["message"]
    assert r.json()["ok"] is False and "tts-key-77" not in r.text
    assert msg.startswith("接口返回错误：45000001 bad speaker for ****")
    assert msg == "接口返回错误：45000001 " + ("bad speaker for **** " + "y" * 300)[:200]


async def test_tts_probe_without_voices(admin_client, respx_mock):
    await put(admin_client, "tts", base_url=TTS_BASE, model="seed-audio-1.0", enabled=False, api_key="tts-key-77", voices=[])
    r = await _test(admin_client, "tts")
    assert r.json() == {"ok": False, "message": "请先配置至少一个音色"}
    assert len(respx_mock.calls) == 0
    assert (await _items(admin_client))["tts"]["last_test_ok"] is False


async def test_probe_incomplete_409(admin_client):
    r = await _test(admin_client, "outline_llm")
    assert r.status_code == 409 and _code(r) == "config_incomplete"
    # 有地址和模型但没 key，也算不完整
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False)
    r = await _test(admin_client, "outline_llm")
    assert r.status_code == 409 and _code(r) == "config_incomplete"
    assert (await _items(admin_client))["outline_llm"]["last_test_ok"] is None


async def test_probe_web_search_400(admin_client):
    await put(admin_client, "web_search", base_url=BASE, model="", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "web_search")
    assert r.status_code == 400 and _code(r) == "probe_unsupported"
    # 不记录
    item = (await _items(admin_client))["web_search"]
    assert item["last_test_ok"] is None and item["last_test_message"] is None


async def test_probe_requires_admin(client):
    r = await _test(client, "outline_llm")
    assert r.status_code == 401


async def test_other_httpx_error_recorded_not_500(admin_client, respx_mock):
    """Timeout/Transport 以外的 httpx 错误（例如响应解码失败）也记成失败，不返回 500。"""
    respx_mock.post(f"{BASE}/chat/completions").mock(side_effect=httpx.DecodingError("bad gzip sk-k1"))
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "outline_llm")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": False, "message": "请求失败：DecodingError"}
    item = (await _items(admin_client))["outline_llm"]
    assert item["last_test_ok"] is False and item["last_test_message"] == "请求失败：DecodingError"


async def test_405_without_v1_hints_incomplete_base_url(admin_client, respx_mock):
    """接口地址少了 /v1：405 空响应时提示地址可能不完整，不自动补 /v1。"""
    route = respx_mock.post("https://r.example.com/chat/completions").respond(405)
    await put(admin_client, "outline_llm", base_url="https://r.example.com", model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "outline_llm")
    assert r.json() == {"ok": False, "message": "HTTP 405。接口地址可能不完整：OpenAI 兼容接口通常以 /v1 结尾"}
    assert route.called


async def test_404_without_v1_hint_keeps_body(admin_client, respx_mock):
    respx_mock.get("https://r.example.com/api/models").respond(404, text="not found")
    await put(admin_client, "image_gen", base_url="https://r.example.com/api", model="img-1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "image_gen")
    assert r.json()["message"] == "HTTP 404：not found。接口地址可能不完整：OpenAI 兼容接口通常以 /v1 结尾"


async def test_405_with_v1_no_hint(admin_client, respx_mock):
    respx_mock.post(f"{BASE}/chat/completions").respond(405)
    await put(admin_client, "outline_llm", base_url=BASE, model="m1", enabled=False, api_key="sk-k1")
    r = await _test(admin_client, "outline_llm")
    assert r.json() == {"ok": False, "message": "HTTP 405"}


async def test_tts_404_no_v1_hint(admin_client, respx_mock):
    respx_mock.post(f"{TTS_BASE}/api/v3/tts/create").respond(404)
    await put(admin_client, "tts", base_url=TTS_BASE, model="seed-audio-1.0", enabled=False, api_key="tts-key-77", voices=VOICES)
    r = await _test(admin_client, "tts")
    assert r.json() == {"ok": False, "message": "HTTP 404"}
