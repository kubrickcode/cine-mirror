# TMDB API는 초당 50 요청 허용하나, 단일 프로세스가 폭주하지 않도록 보수적으로 제한한다.
API_CONCURRENCY = 4
# TMDB ToS: 캐시 보존 기간은 최대 6개월.
CACHE_TTL_MONTHS = 6
# 상위 5만 편이 국내 사용자 검색 요구의 98%+ 를 커버한다는 분석 기반.
SEARCH_INDEX_SIZE = 50_000
