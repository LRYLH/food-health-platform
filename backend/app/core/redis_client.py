from collections.abc import Generator

from redis import Redis

from .config import settings


redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


def get_redis() -> Generator[Redis, None, None]:
    yield redis_client
