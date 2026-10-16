FROM python:3.12-slim

# uv 版本与本地生成 uv.lock 的版本一致
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 先只装依赖（不含 dev 组），代码变动时能复用这一层缓存
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# 用非 root 用户运行；代码和依赖保持 root 所有、只读即可（字节码已在构建时编译）
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# 依次：数据库迁移 -> 初始化管理员 -> 启动服务；任何一步失败都会让容器退出。
# 后端端口不对外暴露，只有同一网络里的 nginx 能访问，所以信任所有转发 IP。
CMD ["sh", "-c", "alembic upgrade head && python -m app.cli bootstrap && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
