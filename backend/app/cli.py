"""命令行工具。

`python -m app.cli bootstrap`：按 .env 里的 INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD
建第一个管理员。容器每次启动都会执行，所以重复运行不会出错（第二次起输出 noop）。
"""

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import PASSWORD_MIN, check_username, normalize_username
from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import User, UserRole, UserStatus
from app.security import hash_password

ENV_MISSING_MSG = "请在 .env 中设置 INITIAL_ADMIN_USERNAME 和 INITIAL_ADMIN_PASSWORD"


async def _has_active_admin(db: AsyncSession) -> bool:
    stmt = (
        select(User.id)
        .where(User.role == UserRole.admin, User.status == UserStatus.active)
        .limit(1)
    )
    return (await db.scalar(stmt)) is not None


async def bootstrap_admin(db: AsyncSession, username: str | None, password: str | None) -> str:
    """确保有一个正常状态的管理员，返回 "created"、"promoted" 或 "noop"。

    配置不完整或不合规时抛 SystemExit（消息里不带密码）。
    """
    name = normalize_username(username or "")
    has_password = bool(password and password.strip())
    has_admin = await _has_active_admin(db)

    if not name:
        if has_admin:
            return "noop"
        raise SystemExit(ENV_MISSING_MSG)
    if not has_admin and not has_password:
        raise SystemExit(ENV_MISSING_MSG)

    # 用户名不区分大小写
    stmt = select(User).where(func.lower(User.username) == name.lower())
    user = await db.scalar(stmt)
    if user is not None:
        if user.role == UserRole.admin and user.status == UserStatus.active:
            return "noop"
        # 提升为管理员，但不改密码：这个人已经有自己的密码了
        user.role = UserRole.admin
        user.status = UserStatus.active
        await db.commit()
        return "promoted"

    if not has_password:
        raise SystemExit(ENV_MISSING_MSG)
    try:
        name = check_username(name)
    except ValueError as e:
        raise SystemExit(f"INITIAL_ADMIN_USERNAME 不合法：{e}") from None
    assert password is not None
    if len(password) < PASSWORD_MIN:
        raise SystemExit(f"INITIAL_ADMIN_PASSWORD 至少需要 {PASSWORD_MIN} 位")

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
