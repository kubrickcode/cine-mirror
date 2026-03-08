# data-collector

TMDB 검증 스파이크를 위한 독립 데이터 수집 서비스입니다.

## 요구 사항

- Python 3.12
- `uv`
- devcontainer rebuild

## 시작하기

1. devcontainer를 rebuild 하여 `postgres`, `redis` 서비스를 함께 기동합니다.
2. `data-collector/.env.example`을 `data-collector/.env`로 복사하고 `TMDB_API_KEY`를 채웁니다.
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
