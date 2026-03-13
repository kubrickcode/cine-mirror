"""FastStream Redis 브로커 단일 인스턴스."""

from faststream.redis import RedisBroker

from src.config import settings

broker = RedisBroker(settings.redis_url)
