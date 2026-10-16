from fastapi import Request
from redis.asyncio import Redis


def create_redis(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis
