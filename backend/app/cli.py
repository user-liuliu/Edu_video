"""命令行工具。

`python -m app.cli bootstrap`：按 .env 里的 INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD
建第一个管理员。容器每次启动都会执行，所以重复运行不会出错（第二次起输出 noop）。
"""

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import PASSWORD_MAX, PASSWORD_MIN, check_username, normalize_username
from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import User, UserRole, UserStatus
from app.security import hash_password, verify_password

ENV_MISSING_MSG = "请在 .env 中设置 INITIAL_ADMIN_USERNAME 和 INITIAL_ADMIN_PASSWORD"
NAME_TAKEN_MSG = "用户名已被其他账号占用且密码不匹配，请更换 INITIAL_ADMIN_USERNAME 或手动处理"


async def _has_active_admin(db: AsyncSession) -> bool:
    stmt = (
        select(User.id)
        .where(User.role == UserRole.admin, User.status == UserStatus.active)
        .limit(1)
    )
    return (await db.scalar(stmt)) is not None


async def bootstrap_admin(db: AsyncSession, username: str | None, password: str | None) -> str:
    """确保有一个正常状态的管理员，返回 "created"、"promoted" 或 "noop"。

    规则（按顺序）：
    1. 已有任何正常状态（active）的管理员：返回 "noop"，不碰任何用户。
       容器每次启动都会运行，这样不会把管理员手动禁用的账号重新启用。
    2. 没有正常状态的管理员，且用户名或密码缺失/空白：抛 SystemExit(ENV_MISSING_MSG)。
    3. 同名用户已存在（不区分大小写）：只有密码校验通过才提升为 admin/active（不改密码），
       返回 "promoted"；否则抛 SystemExit(NAME_TAKEN_MSG)，不改动该用户，
       防止别人先注册同名账号、再借 bootstrap 拿到管理员权限。
    4. 同名用户不存在：校验用户名规则和密码长度（8–128 位），创建正常状态的管理员，返回 "created"。

    所有 SystemExit 消息都不带密码。
    """
    if await _has_active_admin(db):
        return "noop"

    name = normalize_username(username or "")
    if not name or not password or not password.strip():
        raise SystemExit(ENV_MISSING_MSG)

    # 用户名不区分大小写
    stmt = select(User).where(func.lower(User.username) == name.lower())
    user = await db.scalar(stmt)
    if user is not None:
        if not verify_password(password, user.password_hash):
            raise SystemExit(NAME_TAKEN_MSG)
        # 密码对得上，说明就是部署者本人的账号：提升为管理员，不改密码
        user.role = UserRole.admin
        user.status = UserStatus.active
        await db.commit()
        return "promoted"

    try:
        name = check_username(name)
    except ValueError as e:
        raise SystemExit(f"INITIAL_ADMIN_USERNAME 不合法：{e}") from None
    if len(password) < PASSWORD_MIN:
        raise SystemExit(f"INITIAL_ADMIN_PASSWORD 至少需要 {PASSWORD_MIN} 位")
    if len(password) > PASSWORD_MAX:
        raise SystemExit(f"INITIAL_ADMIN_PASSWORD 不能超过 {PASSWORD_MAX} 位")

    db.add(
        User(
            username=name,
            password_hash=hash_password(password),
            role=UserRole.admin,
            status=UserStatus.active,
        )
    )
    await db.commit()
    return "created"


async def _run_bootstrap() -> str:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as session:
            return await bootstrap_admin(
                session, settings.initial_admin_username, settings.initial_admin_password
            )
    finally:
        # 在事件循环关闭前释放连接，避免 Windows 上 asyncpg 退出时报 "Event loop is closed"
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="按 .env 建第一个管理员（可重复执行）")
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        print(asyncio.run(_run_bootstrap()))


if __name__ == "__main__":
    main()
