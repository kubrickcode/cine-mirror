"""FastStream Redis 브로커 단일 진입점."""

import os

from faststream.redis import RedisBroker

# Constraint: TestRedisBroker가 런타임에 연결을 mock하므로 테스트 환경에서 폴백이 안전하다.
# 실 서비스에서는 기동 전 REDIS_URL 환경 변수 설정이 필수다.
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

broker = RedisBroker(_REDIS_URL)
