from typing import Any

import redis.asyncio as aioredis


# redis = aioredis.from_url(url="redis://localhost:6379")
# redis = aioredis.from_url(url="redis://192.168.7.172:6379")
redis = aioredis.from_url(url="redis://45.114.85.18:6379")


class RedisBackend:
    async def get(self, key: str) -> Any:
        return await redis.get(key)

    async def set(self, key: str, value: Any, expire_time: int | None = None) -> Any:
        if expire_time:
            return await redis.setex(key, expire_time, value)
        else:
            return await redis.set(key, value)

    async def delete(self, key: str) -> Any:
        await redis.delete(key)
