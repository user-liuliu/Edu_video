"""安全工具：密码哈希（argon2）、模型 API key 加密（Fernet）与脱敏显示。"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    """密码不匹配或哈希格式不合法时返回 False，不抛异常。"""
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


class SecretDecryptError(Exception):
    """密文无法解密（主密钥不对、密文损坏或格式不合法）。"""


class SecretBox:
    """用主密钥（Fernet key）加解密敏感字符串，例如模型 API key。"""

    def __init__(self, master_key: str) -> None:
        self._fernet = Fernet(master_key)

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except (InvalidToken, ValueError, TypeError):
            # 消息里不带密文或明文；from None 避免把底层异常链带进日志
            raise SecretDecryptError("无法解密密文") from None


def mask_secret(plain: str) -> str:
    """只露出末 4 位；长度不超过 4 时全部遮住。"""
    if len(plain) <= 4:
        return "****"
    return "****" + plain[-4:]
