import fakeredis.aioredis
import pytest

from app.auth import LoginLimiter


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


async def test_user_locked_after_5_failures_and_reset(redis):
    limiter = LoginLimiter(redis)
    for _ in range(4):
        await limiter.record_failure("Teacher_Wang", "1.1.1.1")
    assert not await limiter.is_locked("teacher_wang", "1.1.1.1")
    await limiter.record_failure("Teacher_Wang", "1.1.1.1")
    assert await limiter.is_locked("TEACHER_WANG", "2.2.2.2")  # 按用户名锁定，不区分大小写
    await limiter.reset_user("teacher_wang")
    assert not await limiter.is_locked("teacher_wang", "1.1.1.1")


async def test_ip_locked_after_20_distinct_users(redis):
    limiter = LoginLimiter(redis)
    for i in range(20):
        await limiter.record_failure(f"user{i}", "9.9.9.9")
    assert await limiter.is_locked("anyone", "9.9.9.9")
    assert not await limiter.is_locked("anyone", "8.8.8.8")


async def test_keys_and_expiry(redis):
    limiter = LoginLimiter(redis)
    await limiter.record_failure("Teacher_Wang", "1.1.1.1")
    assert await redis.get("login_fail:u:teacher_wang") == b"1"
    assert await redis.get("login_fail:ip:1.1.1.1") == b"1"
    assert 0 < await redis.ttl("login_fail:u:teacher_wang") <= 900
    assert 0 < await redis.ttl("login_fail:ip:1.1.1.1") <= 900
