import importlib

import pytest
from conftest import login
from fastapi import HTTPException
from sqlalchemy import update

from app.auth import require_admin
from app.models import User, UserRole, UserStatus
from app.settings_store import RegistrationSettings, put_registration


async def test_register_creates_pending(client, db):
    r = await client.post(
        "/api/auth/register", json={"username": "Teacher_Wang", "password": "pass1234"}
    )
    assert r.status_code == 201 and r.json()["status"] == "pending"
    body = r.json()
    assert body["username"] == "Teacher_Wang" and body["role"] == "teacher"
    assert set(body) == {"id", "username", "role", "status", "created_at"}  # 不带密码或哈希
    assert (await client.get("/api/auth/me")).status_code == 401  # 注册后不自动登录


async def test_register_duplicate_case_and_space(client, make_user):
    await make_user("teacher_wang")
    r = await client.post(
        "/api/auth/register", json={"username": " Teacher_Wang ", "password": "pass1234"}
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "username_taken"


async def test_register_duplicate_race_maps_integrity_error(client, make_user, monkeypatch):
    """查重通过后插入时撞上唯一索引（并发注册），也返回 409 username_taken。"""
    # app.auth 包里导出了同名的 router 对象，这里要拿模块本身
    auth_router = importlib.import_module("app.auth.router")

    async def _never_taken(db, name):
        return False

    monkeypatch.setattr(auth_router, "_username_taken", _never_taken)
    await make_user("teacher_wang")
    r = await client.post(
        "/api/auth/register", json={"username": "TEACHER_WANG", "password": "pass1234"}
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "username_taken"


@pytest.mark.parametrize(
    "username,password",
    [("ab", "pass1234"), ("a" * 33, "pass1234"), ("bad name", "pass1234"), ("ok_name", "short")],
)
async def test_register_validation(client, username, password):
    r = await client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 422


async def test_register_accepts_chinese_and_strips_spaces(client, db):
    r = await client.post("/api/auth/register", json={"username": " 王老师_01 ", "password": "pass1234"})
    assert r.status_code == 201 and r.json()["username"] == "王老师_01"


async def test_register_closed(client, db):
    await put_registration(db, RegistrationSettings(open=False))
    r = await client.post(
        "/api/auth/register", json={"username": "Teacher_Wang", "password": "pass1234"}
    )
    assert r.status_code == 403 and r.json()["detail"]["code"] == "registration_closed"


async def test_login_case_insensitive_and_me(client, make_user):
    await make_user("Teacher_Wang", "pass1234")
    r = await client.post(
        "/api/auth/login", json={"username": "teacher_wang ", "password": "pass1234"}
    )
    assert r.status_code == 200 and (await client.get("/api/auth/me")).json()["username"] == "Teacher_Wang"
    assert set(r.json()) == {"id", "username", "role", "status", "created_at"}


async def test_login_wrong_password_and_unknown_user_same_error(client, make_user):
    await make_user("t1", "pass1234")
    wrong = await client.post("/api/auth/login", json={"username": "t1", "password": "wrongpass"})
    unknown = await client.post(
        "/api/auth/login", json={"username": "nobody", "password": "pass1234"}
    )
    assert wrong.status_code == 401 and unknown.status_code == 401
    assert wrong.json()["detail"]["code"] == "invalid_credentials"
    assert wrong.json() == unknown.json()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_login_empty_fields_rejected(client):
    r = await client.post("/api/auth/login", json={"username": "", "password": ""})
    assert r.status_code == 422


async def test_login_locked_after_5_failures(client, make_user):
    await make_user("t1", "pass1234")
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"username": "t1", "password": "wrongpass"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"username": "T1", "password": "pass1234"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "login_locked"
    assert r.json()["detail"]["message"] == "登录失败次数过多，请 15 分钟后再试"
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_successful_login_resets_user_failures(client, make_user):
    await make_user("t1", "pass1234")
    for _ in range(4):
        await client.post("/api/auth/login", json={"username": "t1", "password": "wrongpass"})
    await login(client, "t1", "pass1234")
    for _ in range(4):
        r = await client.post("/api/auth/login", json={"username": "t1", "password": "wrongpass"})
        assert r.status_code == 401
    await login(client, "t1", "pass1234")


async def test_logout_clears_session(client, make_user):
    await make_user("t1", "pass1234")
    await login(client, "t1", "pass1234")
    assert (await client.get("/api/auth/me")).status_code == 200
    r = await client.post("/api/auth/logout")
    assert r.status_code == 204
    r = await client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "not_authenticated"


async def test_pending_user_blocked_from_active_routes(client, make_user):
    await make_user("p1", status="pending")
    await login(client, "p1", "pass1234")
    r = await client.get("/api/_test/active")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_pending"


@pytest.mark.parametrize(
    "status,code", [("rejected", "account_rejected"), ("disabled", "account_disabled")]
)
async def test_inactive_user_blocked_from_active_routes(client, make_user, status, code):
    await make_user("u1", status=status)
    await login(client, "u1", "pass1234")  # 任何状态只要密码对都能登录
    r = await client.get("/api/_test/active")
    assert r.status_code == 403 and r.json()["detail"]["code"] == code


async def test_active_user_passes_and_anonymous_rejected(client, make_user):
    r = await client.get("/api/_test/active")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "not_authenticated"
    await make_user("a1")
    await login(client, "a1", "pass1234")
    r = await client.get("/api/_test/active")
    assert r.status_code == 200 and r.json()["username"] == "a1"


async def test_require_admin():
    teacher = User(username="t1", role=UserRole.teacher, status=UserStatus.active)
    admin = User(username="ad", role=UserRole.admin, status=UserStatus.active)
    with pytest.raises(HTTPException) as exc:
        await require_admin(teacher)
    assert exc.value.status_code == 403 and exc.value.detail["code"] == "forbidden"
    assert await require_admin(admin) is admin


async def test_session_invalidated_when_session_version_bumps(client, db, make_user):
    user = await make_user("t1", "pass1234")
    user_id = user.id
    await login(client, "t1", "pass1234")
    assert (await client.get("/api/auth/me")).status_code == 200
    await db.execute(
        update(User).where(User.id == user_id).values(session_version=User.session_version + 1)
    )
    await db.commit()
    r = await client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "not_authenticated"
