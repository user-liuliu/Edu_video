import httpx
from fastapi import Request


def create_http() -> httpx.AsyncClient:
    """应用共用的 HTTP 客户端（调用模型接口等）；应用关闭时 aclose。"""
    return httpx.AsyncClient(timeout=20)


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http
