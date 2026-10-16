import pytest
from sqlalchemy import func, select

from app.cli import bootstrap_admin
from app.models import User, UserRole, UserStatus
from app.security import verify_password

ENV_MISSING_MSG = "请在 .env 中设置 INITIAL_ADMIN_USERNAME 和 INITIAL_ADMIN_PASSWORD"


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


async def test_promotes_existing_pending_user_keeps_password(db, make_user):
    await make_user("teacher_wang", password="oldpass12", status="pending")
    # 用户名大小写不同、密码不同，也算同一个人；不改密码
    assert await bootstrap_admin(db, "Teacher_Wang", "newpass12") == "promoted"
    [user] = await _users(db)
    assert user.role == UserRole.admin and user.status == UserStatus.active
    assert verify_password("oldpass12", user.password_hash)
    assert not verify_password("newpass12", user.password_hash)


async def test_promotes_existing_user_without_password(db, make_user):
    """已有管理员时，只给用户名也能把现有用户提升为管理员。"""
    await make_user("boss", role="admin")
    await make_user("teacher_li", status="disabled")
    assert await bootstrap_admin(db, "teacher_li", None) == "promoted"
    count = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.admin, User.status == UserStatus.active
        )
    )
    assert count == 2


@pytest.mark.parametrize(
    ("username", "password"),
    [(None, None), ("admin1", None), (None, "adminpass1"), ("  ", "adminpass1"), ("admin1", "  ")],
)
async def test_exits_when_no_admin_and_env_missing(db, make_user, username, password):
    await make_user("t1")  # 有普通老师、但没有正常状态的管理员
    await make_user("old_admin", role="admin", status="disabled")
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, username, password)
    assert str(exc.value) == ENV_MISSING_MSG
    assert len(await _users(db)) == 2


@pytest.mark.parametrize("username", [None, "", "   "])
async def test_noop_when_admin_exists_and_env_missing(db, make_user, username):
    await make_user("boss", role="admin")
    assert await bootstrap_admin(db, username, None) == "noop"
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


async def test_exits_when_new_user_without_password(db, make_user):
    """已有管理员、给了新用户名但没给密码：不能建没有密码的账号。"""
    await make_user("boss", role="admin")
    with pytest.raises(SystemExit) as exc:
        await bootstrap_admin(db, "newadmin", None)
    assert str(exc.value) == ENV_MISSING_MSG
    assert len(await _users(db)) == 1


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
