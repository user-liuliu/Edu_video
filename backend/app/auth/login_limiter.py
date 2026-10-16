"""登录失败次数限制：按用户名和按 IP 分别计数，窗口内达到阈值就锁定。"""

from redis.asyncio import Redis
from redis.exceptions import WatchError


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

    async def _bump(self, *keys: str) -> list[int]:
        """一次 MULTI/EXEC 原子地给每个 key 加一；key 不存在时先建成 0 并设过期时间。

        已存在的 key 不会被重置过期时间，也不会出现没有过期时间的 key。
        """
        async with self._redis.pipeline(transaction=True) as pipe:
            for key in keys:
                pipe.set(key, 0, ex=self._window, nx=True)
                pipe.incr(key)
            results = await pipe.execute()
        return [int(v) for v in results[1::2]]

    async def is_locked(self, username: str, ip: str) -> bool:
        user_count, ip_count = await self._redis.mget(self._user_key(username), self._ip_key(ip))
        return int(user_count or 0) >= self._user_threshold or int(ip_count or 0) >= self._ip_threshold

    async def reserve_attempt(self, username: str, ip: str) -> bool:
        """先占用一次尝试再校验密码，并发请求也不能绕过阈值。超过阈值返回 False。"""
        user_count, ip_count = await self._bump(self._user_key(username), self._ip_key(ip))
        return user_count <= self._user_threshold and ip_count <= self._ip_threshold

    async def release_success(self, username: str, ip: str) -> None:
        """登录成功：清掉用户名计数，并退还这次占用的 IP 次数（不低于 0，到 0 就删除）。"""
        await self._redis.delete(self._user_key(username))
        ip_key = self._ip_key(ip)
        for _ in range(3):
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(ip_key)
                    count = int(await pipe.get(ip_key) or 0)
                    pipe.multi()
                    if count > 1:
                        pipe.decr(ip_key)  # key 存在时 DECR 保留原过期时间
                    else:
                        pipe.delete(ip_key)
                    await pipe.execute()
                return
            except WatchError:
                continue  # 期间有别的请求改了计数，重试；多次冲突就放弃退还（偏保守）

    async def record_failure(self, username: str, ip: str) -> None:
        await self._bump(self._user_key(username), self._ip_key(ip))

    async def reset_user(self, username: str) -> None:
        await self._redis.delete(self._user_key(username))
