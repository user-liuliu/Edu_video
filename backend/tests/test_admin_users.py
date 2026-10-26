import asyncio
import importlib
import uuid

from conftest import login
from sqlalchemy import func, select

from app.models import User, UserRole, UserStatus


def _code(r) -> str:
    return r.json()["detail"]["code"]


def _admin_requests(uid) -> list[tuple[str, str, dict | None]]:
    """所有管理后台接口（带合法的请求体），用来检查每个接口都要求管理员。"""
    return [
        ("GET", "/api/admin/users", None),
        ("POST", f"/api/admin/users/{uid}/actions", {"action": "disable"}),
        ("POST", f"/api/admin/users/{uid}/password", {"password": "newpass5678"}),
        ("PUT", f"/api/admin/users/{uid}/role", {"role": "admin"}),
        ("GET", "/api/admin/settings/registration", None),
        ("PUT", "/api/admin/settings/registration", {"open": False}),
    ]


async def test_admin_routes_require_admin(client, make_user):
    teacher = await make_user("t1")
    await make_user("admin_p", role="admin", status="pending")
    requests = _admin_requests(teacher.id)

    for method, path, body in requests:
        r = await client.request(method, path, json=body)
        assert r.status_code == 401 and _code(r) == "not_authenticated", (method, path)

    await login(client, "t1", "pass1234")
    for method, path, body in requests:
        r = await client.request(method, path, json=body)
        assert r.status_code == 403 and _code(r) == "forbidden", (method, path)

    await login(client, "admin_p", "pass1234")
    for method, path, body in requests:
        r = await client.request(method, path, json=body)
        assert r.status_code == 403 and _code(r) == "account_pending", (method, path)

    # 上面的请求都没有生效：t1 仍能用原密码登录，注册仍然开放
    await login(client, "t1", "pass1234")
    assert (await client.get("/api/auth/me")).json()["status"] == "active"
    r = await client.post("/api/auth/register", json={"username": "new_one", "password": "pass1234"})
    assert r.status_code == 201


async def test_list_pending_first_and_filter(admin_client, make_user):
    # pending 用户最早创建：只按 created_at 倒序的话它会排在最后
    await make_user("zhang_p", status="pending")
    await make_user("teacher_wang")
    await make_user("teacher_li")

    r = await admin_client.get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert [u["username"] for u in body["items"]] == [
        "zhang_p",
        "teacher_li",
        "teacher_wang",
        "admin1",
    ]
    assert body["items"][0]["status"] == "pending"
    assert set(body["items"][0]) == {"id", "username", "role", "status", "created_at", "video_count", "ppt_count", "project_count"}

    r = await admin_client.get("/api/admin/users", params={"status": "active"})
    body = r.json()
    assert body["total"] == 3
    assert {u["username"] for u in body["items"]} == {"teacher_wang", "teacher_li", "admin1"}
    assert all(u["status"] == "active" for u in body["items"])

    r = await admin_client.get("/api/admin/users", params={"q": "WANG"})
    body = r.json()
    assert body["total"] == 1 and [u["username"] for u in body["items"]] == ["teacher_wang"]

    # 通配符按普通字符处理
    r = await admin_client.get("/api/admin/users", params={"q": "%"})
    assert r.json() == {"items": [], "total": 0}

    # 分页：total 仍是全部数量
    r = await admin_client.get("/api/admin/users", params={"page": 2, "page_size": 3})
    body = r.json()
    assert body["total"] == 4 and [u["username"] for u in body["items"]] == ["admin1"]

    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}, {"status": "nope"}):
        assert (await admin_client.get("/api/admin/users", params=params)).status_code == 422


async def test_approve_pending_and_rejected(admin_client, admin_user, make_user, db):
    pending = await make_user("p1", status="pending")
    rejected = await make_user("r1", status="rejected")

    for user in (pending, rejected):
        r = await admin_client.post(
            f"/api/admin/users/{user.id}/actions", json={"action": "approve"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "active" and r.json()["id"] == str(user.id)

        await db.refresh(user)
        assert user.status == UserStatus.active
        assert user.reviewed_by == admin_user.id
        assert user.reviewed_at is not None


async def test_reject_disable_enable_and_not_found(admin_client, admin_user, make_user, db):
    pending = await make_user("p1", status="pending")
    r = await admin_client.post(f"/api/admin/users/{pending.id}/actions", json={"action": "reject"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    await db.refresh(pending)
    assert pending.reviewed_by == admin_user.id and pending.reviewed_at is not None

    teacher = await make_user("t1")
    r = await admin_client.post(f"/api/admin/users/{teacher.id}/actions", json={"action": "disable"})
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    r = await admin_client.post(f"/api/admin/users/{teacher.id}/actions", json={"action": "enable"})
    assert r.status_code == 200 and r.json()["status"] == "active"

    missing = uuid.uuid4()
    for method, path, body in _admin_requests(missing)[1:4]:
        r = await admin_client.request(method, path, json=body)
        assert r.status_code == 404 and _code(r) == "user_not_found", (method, path)

    r = await admin_client.post(f"/api/admin/users/{teacher.id}/actions", json={"action": "nope"})
    assert r.status_code == 422


async def test_invalid_transition_409(admin_client, make_user):
    active = await make_user("t1")
    r = await admin_client.post(f"/api/admin/users/{active.id}/actions", json={"action": "approve"})
    assert r.status_code == 409 and _code(r) == "invalid_transition"

    for action in ("reject", "enable"):
        r = await admin_client.post(
            f"/api/admin/users/{active.id}/actions", json={"action": action}
        )
        assert r.status_code == 409 and _code(r) == "invalid_transition", action

    rejected = await make_user("r1", status="rejected")
    for action in ("reject", "disable", "enable"):
        r = await admin_client.post(
            f"/api/admin/users/{rejected.id}/actions", json={"action": action}
        )
        assert r.status_code == 409 and _code(r) == "invalid_transition", action


async def test_disable_kicks_existing_session(app, admin_client, make_user, make_client):
    user = await make_user("t1")
    t = make_client(app)
    await login(t, "t1", "pass1234")
    assert (await t.get("/api/auth/me")).status_code == 200

    r = await admin_client.post(f"/api/admin/users/{user.id}/actions", json={"action": "disable"})
    assert r.status_code == 200
    assert (await t.get("/api/auth/me")).status_code == 401


async def test_reset_password_invalidates_and_new_works(app, admin_client, make_user, make_client):
    user = await make_user("t1")
    t = make_client(app)
    await login(t, "t1", "pass1234")

    r = await admin_client.post(
        f"/api/admin/users/{user.id}/password", json={"password": "newpass5678"}
    )
    assert r.status_code == 204 and r.content == b""

    assert (await t.get("/api/auth/me")).status_code == 401
    fresh = make_client(app)
    r = await fresh.post("/api/auth/login", json={"username": "t1", "password": "pass1234"})
    assert r.status_code == 401 and _code(r) == "invalid_credentials"
    await login(fresh, "t1", "newpass5678")
    assert (await fresh.get("/api/auth/me")).json()["username"] == "t1"


async def test_reset_password_too_short_422(admin_client, make_user):
    user = await make_user("t1")
    for password in ("short", "x" * 129):
        r = await admin_client.post(
            f"/api/admin/users/{user.id}/password", json={"password": password}
        )
        assert r.status_code == 422, password


async def test_last_admin_cannot_demote_or_disable_self(admin_client, admin_user, make_user, db):
    # 待审核或已停用的管理员不算"正常状态的管理员"
    await make_user("admin_p", role="admin", status="pending")
    await make_user("admin_d", role="admin", status="disabled")

    r = await admin_client.put(f"/api/admin/users/{admin_user.id}/role", json={"role": "teacher"})
    assert r.status_code == 409 and _code(r) == "last_admin"
    assert r.json()["detail"]["message"] == "系统至少需要保留一个管理员"

    r = await admin_client.post(
        f"/api/admin/users/{admin_user.id}/actions", json={"action": "disable"}
    )
    assert r.status_code == 409 and _code(r) == "last_admin"
    assert r.json()["detail"]["message"] == "系统至少需要保留一个管理员"

    # 两次操作都已回滚：仍是正常状态的管理员，会话也没有失效
    await db.refresh(admin_user)
    assert admin_user.role == UserRole.admin and admin_user.status == UserStatus.active
    assert (await admin_client.get("/api/admin/users")).status_code == 200


async def test_second_admin_allows_demotion(app, admin_client, admin_user, make_user, make_client):
    second = await make_user("t2")
    r = await admin_client.put(f"/api/admin/users/{second.id}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"

    r = await admin_client.put(f"/api/admin/users/{admin_user.id}/role", json={"role": "teacher"})
    assert r.status_code == 200 and r.json()["role"] == "teacher"
    # 降级后已不是管理员
    r = await admin_client.get("/api/admin/users")
    assert r.status_code == 403 and _code(r) == "forbidden"

    # 新管理员是唯一的管理员了：同样不能把自己降级
    c2 = make_client(app)
    await login(c2, "t2", "pass1234")
    r = await c2.put(f"/api/admin/users/{second.id}/role", json={"role": "teacher"})
    assert r.status_code == 409 and _code(r) == "last_admin"
    r = await c2.put(f"/api/admin/users/{second.id}/role", json={"role": "nope"})
    assert r.status_code == 422


async def test_set_role_requires_active_target(admin_client, make_user, db):
    """只有正常状态的账号可以改角色：待审核的用户不能直接设为管理员。"""
    pending = await make_user("p1", status="pending")
    r = await admin_client.put(f"/api/admin/users/{pending.id}/role", json={"role": "admin"})
    assert r.status_code == 409 and _code(r) == "invalid_transition"
    assert r.json()["detail"]["message"] == "只有正常状态的账号可以修改角色"
    await db.refresh(pending)
    assert pending.role == UserRole.teacher


async def test_concurrent_demotions_keep_one_admin(
    app, admin_client, admin_user, make_user, make_client, db, monkeypatch
):
    """两个管理员同时把对方降级：只能有一个成功，系统里仍保留一个正常管理员。"""
    # 让两个请求在锁住各自目标之后互相等一下，确保两个事务真的重叠（否则调度上可能恰好串行）。
    # 加锁正确时第二个请求会卡在锁上到不了这里，第一个请求等待超时后继续。
    user_actions = importlib.import_module("app.admin.user_actions")
    original_lock_target = user_actions._lock_target
    arrived = 0
    both_inside = asyncio.Event()

    async def _gated_lock_target(db, target_id):
        nonlocal arrived
        user = await original_lock_target(db, target_id)
        arrived += 1
        if arrived >= 2:
            both_inside.set()
        try:
            await asyncio.wait_for(both_inside.wait(), timeout=0.5)
        except TimeoutError:
            pass
        return user

    monkeypatch.setattr(user_actions, "_lock_target", _gated_lock_target)
    second = await make_user("admin2", role="admin")
    c2 = make_client(app)
    await login(c2, "admin2", "pass1234")

    r1, r2 = await asyncio.gather(
        admin_client.put(f"/api/admin/users/{second.id}/role", json={"role": "teacher"}),
        c2.put(f"/api/admin/users/{admin_user.id}/role", json={"role": "teacher"}),
    )
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses[0] == 200 and statuses[1] in (403, 409), (r1.text, r2.text)
    count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin, User.status == UserStatus.active)
    )
    assert count == 1


async def test_registration_toggle(admin_client, client):
    r = await admin_client.get("/api/admin/settings/registration")
    assert r.status_code == 200 and r.json() == {"open": True}

    r = await admin_client.put("/api/admin/settings/registration", json={"open": False})
    assert r.status_code == 200 and r.json() == {"open": False}
    assert (await admin_client.get("/api/admin/settings/registration")).json() == {"open": False}

    r = await client.post("/api/auth/register", json={"username": "new_one", "password": "pass1234"})
    assert r.status_code == 403 and _code(r) == "registration_closed"

    r = await admin_client.put("/api/admin/settings/registration", json={"open": True})
    assert r.status_code == 200
    r = await client.post("/api/auth/register", json={"username": "new_one", "password": "pass1234"})
    assert r.status_code == 201


async def test_admin_project_total_counts_video_and_ppt_once_with_owner_breakdown(admin_client,make_user,db):
    from app.models import VideoProject
    from app.presentations.models import PptProject
    teacher=await make_user('project_owner');other=await make_user('ppt_only');empty=await make_user('empty_projects')
    video=VideoProject(owner_id=teacher.id,title='视频草稿',prompt='视频需求',form_values={})
    a=PptProject(owner_id=teacher.id,title='PPT草稿',prompt='需求',status='draft')
    b=PptProject(owner_id=teacher.id,title='PPT成品',prompt='需求',status='ready',history=[{'revision':1,'pages':[{'id':'old'}]},{'revision':2,'pages':[{'id':'older'}]}])
    db.add_all([video,a,b,PptProject(owner_id=other.id,title='独立课件',prompt='需求')]);await db.commit()
    result=await admin_client.get('/api/admin/users');assert result.status_code==200,result.text
    users={u['username']:u for u in result.json()['items']}
    assert (users['project_owner']['project_count'],users['project_owner']['video_count'],users['project_owner']['ppt_count'])==(3,1,2)
    assert (users['ppt_only']['project_count'],users['ppt_only']['video_count'],users['ppt_only']['ppt_count'])==(1,0,1)
    assert (users['empty_projects']['project_count'],users['empty_projects']['video_count'],users['empty_projects']['ppt_count'])==(0,0,0)
    filtered=(await admin_client.get('/api/admin/users',params={'q':'project_owner','page_size':1})).json()
    assert filtered['total']==1 and filtered['items'][0]['project_count']==3
    await db.delete(a);await db.commit()
    filtered=(await admin_client.get('/api/admin/users',params={'q':'project_owner'})).json()
    assert (filtered['items'][0]['project_count'],filtered['items'][0]['ppt_count'])==(2,1)
