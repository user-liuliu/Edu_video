from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def api_error(status: int, code: str, message: str) -> HTTPException:
    """统一错误格式：{"detail": {"code": ..., "message": ...}}。"""
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求体校验失败时只返回 type / loc / msg，不带 input、ctx、url，
    免得把请求里的密码、API key 原样写回响应。"""
    errors = [
        {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})
