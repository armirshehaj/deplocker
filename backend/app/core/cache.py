from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.conf import settings


class RedisManager:
    def __init__(self) -> None:
        self.redis_pool = ConnectionPool(
            host=settings.REDIS_HOST,
            password=settings.REDIS_PASSWORD,
            port=settings.REDIS_PORT,
            max_connections=100,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        self.client = Redis(connection_pool=self.redis_pool)

    async def arrpop(self, key: str, value: Any, path: str = "$") -> None:
        json_array_content: list = await self.client.json().get(key, path)  # type: ignore[misc]
        searching_value_index = json_array_content.index(value)
        await self.client.json().arrpop(key, path, searching_value_index)  # type: ignore[misc]


redis = RedisManager()
