# data-collector

TMDB 검증 스파이크를 위한 독립 데이터 수집 서비스입니다.

## 요구 사항

- Python 3.12
- `uv`
- devcontainer rebuild

## 시작하기

1. devcontainer를 rebuild 하여 `postgres`, `redis` 서비스를 함께 기동합니다.
2. devcontainer 안에서는 `DATABASE_URL`, `REDIS_URL`이 자동 주입됩니다. `data-collector/.env.example`을 `data-collector/.env`로 복사한 뒤 `TMDB_ACCESS_TOKEN`만 채우면 됩니다. (TMDB 대시보드 → Settings → API → "API 읽기 액세스 토큰")
3. `data-collector/` 디렉터리에서 의존성을 설치합니다.

```bash
cd data-collector
uv sync
```

4. Alembic 연결과 기본 마이그레이션 경로를 확인합니다.

```bash
uv run alembic upgrade head
```

향후 스키마 정의는 `SQLAlchemy 2.x Core` 메타데이터를 기준으로 추가합니다.

## 개발 환경 확인

PostgreSQL 연결:

```bash
psql "$DATABASE_URL" -c '\l'
```

Redis 연결:

```bash
redis-cli -u "$REDIS_URL" ping
```

의존성 동기화:

```bash
cd data-collector
uv sync
```

## 서비스 기동

```bash
cd data-collector
just run          # 스케줄러 + 이벤트 소비자 기동
just run-small    # 소규모 테스트 (SEARCH_INDEX_SIZE=100)
```

기동 시 다음 로그가 출력되어야 합니다.

```
Scheduler started
FastStream connected
```

## 주요 명령어

| 명령어          | 설명                       |
| --------------- | -------------------------- |
| `just sync`     | 의존성 설치                |
| `just migrate`  | DB 마이그레이션 적용       |
| `just run`      | 서비스 기동                |
| `just run-small`| 소규모(100건) 테스트 실행  |
| `just test`     | 전체 테스트 실행           |
| `just lint`     | 린트 + 포맷 검사           |
| `just lint-fix` | 린트 자동 수정             |

## ⚠️ 멀티 인스턴스 배포 주의

`daily_export_job`과 `metadata_refresh_job`은 단일 인스턴스 실행을 가정합니다. 여러 인스턴스를 동시에 기동하면 동일 작업이 중복 실행됩니다. 멀티 인스턴스 환경에서는 Redis SETNX 또는 PostgreSQL advisory lock 등의 분산 락을 도입해야 합니다.
