---
name: SQLAlchemy Core와 Alembic 채택
description: data-collector와 향후 백엔드 서비스의 DB 접근 계층을 SQLAlchemy Core와 Alembic으로 표준화한다.
status: 수락됨
date: 2026-03-08
supersedes: null
---

# ADR-0001: SQLAlchemy Core와 Alembic 채택

## 맥락

`data-collector`는 TMDB Daily Export 적재, enrichment, 이벤트 소비/발행을 담당하는 독립 서비스다. 이 서비스는 PostgreSQL의 `JSONB`, generated column, partial index, upsert 같은 기능을 직접 활용해야 하고, 이후 `core-film-journal`도 유사한 패턴을 따를 가능성이 높다.

팀 선호도도 명확하다. ORM이 SQL 의미를 숨기는 방향보다 SQL이 드러나는 접근을 선호하며, AI 기반 코딩 환경에서도 명시적 SQL 또는 SQL에 가까운 쿼리 구성이 검토와 수정에 유리하다. 반면 Python 초심자라는 조건 때문에 추상화가 많은 ORM을 추가로 학습하는 비용도 고려해야 했다.

## 결정 요인

- PostgreSQL 고급 기능을 우회 없이 표현할 수 있어야 한다.
- AI와 사람이 함께 쿼리를 읽고 검토하기 쉬워야 한다.
- 마이크로서비스별 마이그레이션 이력을 독립적으로 관리할 수 있어야 한다.
- Python 초심자에게도 추상화 규칙보다 SQL 개념이 더 일관된 학습 경로여야 한다.

## 검토한 선택지

### 선택지 1: SQLModel + Alembic

- 장점: 모델 선언이 간결하고 FastAPI 계열 예제가 많다.
- 단점: 고급 쿼리와 비동기 패턴에서 결국 SQLAlchemy 이해가 필요하고, SQL 의미가 코드에서 덜 드러난다.

### 선택지 2: SQLAlchemy 2.x Core + Alembic

- 장점: SQL 의미를 유지한 채 PostgreSQL 기능을 직접 활용할 수 있고, Alembic과의 결합이 성숙해 있다.
- 단점: 초기 CRUD도 더 명시적으로 작성해야 해서 코드량이 다소 늘어난다.

### 선택지 3: Raw SQL + Alembic

- 장점: SQL 가시성이 가장 높고 데이터베이스 동작을 정확히 통제할 수 있다.
- 단점: 공통 메타데이터, 타입 매핑, 세션 관리까지 모두 수동으로 다뤄야 해 초기 생산성이 떨어진다.

## 결정

DB 접근 계층은 `SQLAlchemy 2.x Core`를 기본으로 사용하고, 마이그레이션은 `Alembic`으로 관리한다. 서비스 스키마는 공용 `MetaData`를 기준으로 정의하며, 복잡한 PostgreSQL 기능은 Core 표현 또는 명시적 SQL로 드러내는 방향을 유지한다.

이 조합은 SQL 가시성과 운영 안정성 사이의 균형이 가장 좋다. `SQLModel`의 간결함은 포기하지만, 장기적으로는 추상화 누수를 줄이고 AI 검토 가능성을 높이는 편이 더 중요하다고 판단했다.

## 결과

- 긍정적: 테이블 정의, 쿼리, 마이그레이션이 모두 PostgreSQL 기능 중심으로 일관되게 정리된다.
- 긍정적: 향후 `core-film-journal`에도 같은 패턴을 적용하기 쉽다.
- 수용한 트레이드오프: 단순 CRUD도 ORM보다 장황해질 수 있다.
- 수용한 트레이드오프: Python 입문 단계에서 SQLAlchemy Core 문법을 별도로 익혀야 한다.

## 관련 문서

- [tmdb-validation-spike 분석](/workspaces/cine-mirror/docs/work/tmdb-validation-spike/analysis.md)
- [tmdb-validation-spike 계획](/workspaces/cine-mirror/docs/work/tmdb-validation-spike/plan.md)
- [movie-project 분석](/workspaces/cine-mirror/docs/epic/movie-project/analysis.md)
