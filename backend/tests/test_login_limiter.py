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


async def test_reserve_attempt_allows_5_then_blocks(redis):
    limiter = LoginLimiter(redis)
    results = [await limiter.reserve_attempt("Teacher_Wang", "1.1.1.1") for _ in range(6)]
    assert results == [True] * 5 + [False]


async def test_reserve_attempt_sets_ttl_on_both_keys(redis):
    limiter = LoginLimiter(redis)
    assert await limiter.reserve_attempt("Teacher_Wang", "1.1.1.1")
    assert 0 < await redis.ttl("login_fail:u:teacher_wang") <= 900
    assert 0 < await redis.ttl("login_fail:ip:1.1.1.1") <= 900
    # 后续请求不重置过期时间
    await redis.expire("login_fail:u:teacher_wang", 100)
    assert await limiter.reserve_attempt("Teacher_Wang", "1.1.1.1")
    assert 0 < await redis.ttl("login_fail:u:teacher_wang") <= 100


async def test_reserve_attempt_ip_threshold(redis):
    limiter = LoginLimiter(redis)
    assert all([await limiter.reserve_attempt(f"user{i}", "9.9.9.9") for i in range(20)])
    assert not await limiter.reserve_attempt("anyone", "9.9.9.9")
    assert await limiter.reserve_attempt("anyone", "8.8.8.8")


async def test_release_success_deletes_user_key_and_decrements_ip(redis):
    limiter = LoginLimiter(redis)
    await limiter.reserve_attempt("other", "1.1.1.1")
    await limiter.reserve_attempt("Teacher_Wang", "1.1.1.1")
    await limiter.release_success("Teacher_Wang", "1.1.1.1")
    assert await redis.exists("login_fail:u:teacher_wang") == 0
    assert await redis.get("login_fail:ip:1.1.1.1") == b"1"
    assert 0 < await redis.ttl("login_fail:ip:1.1.1.1") <= 900
    # 减到 0 时删除 key，不会出现负数或没有过期时间的 key
    await limiter.release_success("other", "1.1.1.1")
    assert await redis.exists("login_fail:ip:1.1.1.1") == 0
    await limiter.release_success("other", "1.1.1.1")
    assert await redis.exists("login_fail:ip:1.1.1.1") == 0


async def test_record_failure_keeps_ttl_on_existing_key(redis):
    limiter = LoginLimiter(redis)
    await limiter.record_failure("t1", "1.1.1.1")
    await redis.expire("login_fail:u:t1", 100)
    await limiter.record_failure("t1", "1.1.1.1")
    assert await redis.get("login_fail:u:t1") == b"2"
    assert 0 < await redis.ttl("login_fail:u:t1") <= 100
