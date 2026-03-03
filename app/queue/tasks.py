from __future__ import annotations
from typing import Any
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

async def enqueue_generate(**payload: Any) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job("generate_card", payload)
    await redis.close()
