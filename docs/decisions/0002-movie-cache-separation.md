---
name: movie_search_cache와 movie_cache 분리
description: 검색 인덱스 캐시와 enrichment 메타데이터 캐시를 별도 테이블로 관리하는 이유
status: 확정됨
---

# 0002: movie_search_cache와 movie_cache 분리

## 맥락

core-film-journal 서비스는 두 종류의 영화 데이터를 외부에서 수신한다.

1. **검색 인덱스** (`search_index.synced`): data-collector의 Daily Export 파이프라인이 수만 건을 배치로 발행. `tmdb_id`, `original_title`, `korean_title`, `popularity`만 포함. 주기적으로 전체 재동기화됨.
2. **enrichment 메타데이터** (`movie.enriched`): 사용자가 저널에 특정 영화를 추가할 때 on-demand로 요청. `poster_path`, `directors` 등 상세 정보 포함. 한 번 수신하면 stable.

## 결정

두 종류의 데이터를 `movie_search_cache`와 `movie_cache` 두 개의 독립 테이블로 관리한다.

## 근거

| 기준 | 단일 테이블 | 분리 테이블 |
|------|------------|------------|
| UPSERT 범위 | 검색 재동기화 시 enrichment 필드를 덮어쓸 위험 | 재동기화가 enrichment 데이터에 영향 없음 |
| 인덱스 전략 | 검색용 GIN trigram + enrichment 조회용 B-tree 충돌 | 각 테이블에 최적화된 인덱스 독립 적용 |
| 데이터 생명주기 | 불일치 (검색 인덱스는 ephemeral, enrichment는 stable) | 생명주기 별로 독립 관리 가능 |
| 확장성 | 수만 건의 검색 레코드와 수백 건의 enriched 레코드가 혼재 | 검색 테이블만 GIN 인덱스 부담을 짐 |

## 트레이드오프

- `journal_entry`가 tmdb_id로 두 캐시를 각각 JOIN해야 함 (Commit 3+).
- `korean_title`, `original_title`, `tmdb_id` 3개 필드가 두 테이블에 중복됨. 이는 CQRS 읽기 모델의 의도된 중복으로 허용함.
- `journal_entry.tmdb_id`는 두 캐시 중 어느 쪽에도 FK를 걸지 않음. enrichment 요청 전 상태에서도 저널 항목을 생성할 수 있어야 하기 때문.

## 결과

Commit 3의 저널 상세 조회에서 `movie_cache LEFT JOIN`을 사용한다. enrichment 완료 전이면 포스터/감독 정보가 null로 반환되고 프론트엔드가 로딩 표시를 담당한다.
