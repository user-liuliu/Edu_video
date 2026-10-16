import pytest
from sqlalchemy import func, select

from app.cli import bootstrap_admin
from app.models import User, UserRole, UserStatus
from app.security import verify_password

ENV_MISSING_MSG = "请在 .env 中设置 INITIAL_ADMIN_USERNAME 和 INITIAL_ADMIN_PASSWORD"
NAME_TAKEN_MSG = "用户名已被其他账号占用且密码不匹配，请更换 INITIAL_ADMIN_USERNAME 或手动处理"


async def _users(db) -> list[User]:
    db.expire_all()
    return list((await db.execute(select(User))).scalars())


async def test_creates_admin_when_none(db):
    assert await bootstrap_admin(db, " Admin_1 ", "adminpass1") == "created"
    [user] = await _users(db)
    assert user.username == "Admin_1"  # 去掉首尾空格，保留大小写
    assert user.role == UserRole.admin and user.status == UserStatus.active
    assert verify_password("adminpass1", user.password_hash)


async def test_idempotent(db):
    assert await bootstrap_admin(db, "admin1", "adminpass1") == "created"
    assert await bootstrap_admin(db, "admin1", "adminpass1") == "noop"
    assert len(await _users(db)) == 1


async def test_promotes_existing_user_when_password_matches(db, make_user):
    """没有正常状态的管理员、同名用户存在且密码对得上：提升为管理员，不改密码。"""
    await make_user("teacher_wang", password="samepass12", status="pending")
    # 用户名大小写不同也算同一个人
    assert await bootstrap_admin(db, "Teacher_Wang", "samepass12") == "promoted"
    [user] = await _users(db)
    assert user.username == "teacher_wang"
    assert user.role == UserRole.admin and user.status == UserStatus.active
    assert verify_password("samepass12", user.password_hash)


async def test_refuses_promotion_when_password_mismatch(db, make_user):
    """同名用户是别人先注册的（密码不同）：拒绝提升，防止借管理员用户名接管账号。"""
    await make_user("teacher_wang", password="theirpass12", status="pending")
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, "Teacher_Wang", "envpass123")
    assert str(exc.value) == NAME_TAKEN_MSG
    assert "envpass123" not in str(exc.value)  # 不回显密码
    [user] = await _users(db)
    assert user.role == UserRole.teacher and user.status == UserStatus.pending
    assert verify_password("theirpass12", user.password_hash)


async def test_noop_when_active_admin_exists_even_if_env_names_other_user(db, make_user):
    """已有正常状态的管理员：不碰任何用户，被管理员禁用的账号不会被重新启用。"""
    await make_user("boss", role="admin")
    await make_user("teacher_li", password="pass1234", status="disabled")
    assert await bootstrap_admin(db, "teacher_li", "pass1234") == "noop"
    users = {u.username: u for u in await _users(db)}
    assert users["teacher_li"].role == UserRole.teacher
    assert users["teacher_li"].status == UserStatus.disabled
    admins = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.admin, User.status == UserStatus.active
        )
    )
    assert admins == 1


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, None),
        ("admin1", None),
        (None, "adminpass1"),
        ("  ", "adminpass1"),
        ("admin1", "  "),
        ("t1", None),  # 同名用户存在也必须给密码
        ("old_admin", ""),
    ],
)
async def test_exits_when_no_admin_and_env_missing(db, make_user, username, password):
    await make_user("t1")  # 有普通老师、但没有正常状态的管理员
    await make_user("old_admin", role="admin", status="disabled")
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, username, password)
    assert str(exc.value) == ENV_MISSING_MSG
    assert len(await _users(db)) == 2


@pytest.mark.parametrize(
    ("username", "password"),
    [(None, None), ("", None), ("   ", None), ("newadmin", None), ("newadmin", "adminpass1")],
)
async def test_noop_when_admin_exists_and_env_missing(db, make_user, username, password):
    """已有正常状态的管理员：无论 .env 给没给、给的是不是新用户名，都不建账号。"""
    await make_user("boss", role="admin")
    assert await bootstrap_admin(db, username, password) == "noop"
    assert len(await _users(db)) == 1


async def test_rejects_short_password(db):
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, "admin1", "short12")
    assert "8" in str(exc.value)
    assert "short12" not in str(exc.value)  # 不回显密码
    assert await _users(db) == []


@pytest.mark.parametrize("username", ["ab", "a" * 33, "bad-name", "有 空格"])
async def test_rejects_invalid_username(db, username):
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, username, "adminpass1")
    assert "INITIAL_ADMIN_USERNAME" in str(exc.value)
    assert await _users(db) == []


async def test_run_bootstrap_reads_settings(db, settings, monkeypatch):
    """命令入口从 settings 读用户名和密码，用自己的引擎连库并在结束时释放。"""
    from app import cli

    patched = settings.model_copy(
        update={"initial_admin_username": "envadmin", "initial_admin_password": "envpass12"}
    )
    monkeypatch.setattr(cli, "get_settings", lambda: patched)
    assert await cli._run_bootstrap() == "created"
    assert await cli._run_bootstrap() == "noop"
    [user] = await _users(db)
    assert user.username == "envadmin" and user.role == UserRole.admin
