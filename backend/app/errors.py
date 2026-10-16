from fastapi import HTTPException


def api_error(status: int, code: str, message: str) -> HTTPException:
    """统一错误格式：{"detail": {"code": ..., "message": ...}}。"""
    return HTTPException(status_code=status, detail={"code": code, "message": message})
