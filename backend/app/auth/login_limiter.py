"""登录失败次数限制：按用户名和按 IP 分别计数，窗口内达到阈值就锁定。"""

from redis.asyncio import Redis


class LoginLimiter:
    def __init__(
        self,
        redis: Redis,
        user_threshold: int = 5,
        ip_threshold: int = 20,
        window_seconds: int = 900,
    ) -> None:
        self._redis = redis
        self._user_threshold = user_threshold
        self._ip_threshold = ip_threshold
        self._window = window_seconds

    @staticmethod
    def _user_key(username: str) -> str:
        return f"login_fail:u:{username.lower()}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"login_fail:ip:{ip}"

    async def is_locked(self, username: str, ip: str) -> bool:
        user_count, ip_count = await self._redis.mget(self._user_key(username), self._ip_key(ip))
        return int(user_count or 0) >= self._user_threshold or int(ip_count or 0) >= self._ip_threshold

    async def record_failure(self, username: str, ip: str) -> None:
        for key in (self._user_key(username), self._ip_key(ip)):
            count = await self._redis.incr(key)
            if count == 1:
                # 第一次失败时开始计时，窗口结束后计数自动清零
                await self._redis.expire(key, self._window)

    async def reset_user(self, username: str) -> None:
        await self._redis.delete(self._user_key(username))
