"""validate_matching 순수 함수 로직 검증 테스트.

10개 시나리오로 정규화·매칭·실패 분류·보고서 계산 로직을 검증한다.
실제 TMDB API 호출 없이 순수 함수만 테스트하여 결정론적 결과를 보장한다.
"""

from validate_matching import (
    FailureType,
    MatchResult,
    MovieEntry,
    build_report,
    check_match,
    classify_failure,
    is_result_match,
    normalize_title,
)


class TestNormalizeTitle:
    def test_removes_punctuation(self) -> None:
        # 콜론·쉼표 등 구두점이 제거되어야 비교 시 오탐이 발생하지 않는다
        assert normalize_title("Kill Bill: Volume 1") == "kill bill volume 1"

    def test_lowercases(self) -> None:
        assert normalize_title("The Dark Knight") == "the dark knight"

    def test_handles_korean(self) -> None:
        # 한국어 제목은 구두점만 제거되고 글자는 보존되어야 한다
        assert normalize_title("신과함께-죄와벌") == "신과함께죄와벌"


class TestIsResultMatch:
    def test_matches_original_title(self) -> None:
        result = {"original_title": "Parasite", "title": "기생충"}
        assert is_result_match(result, "Parasite") is True

    def test_matches_localized_title(self) -> None:
        # TMDB가 한국어 제목을 title 필드로 반환하는 경우
        result = {"original_title": "기생충", "title": "기생충"}
        assert is_result_match(result, "기생충") is True

    def test_returns_false_for_no_match(self) -> None:
        result = {"original_title": "Joker", "title": "조커"}
        assert is_result_match(result, "Batman") is False


class TestClassifyFailure:
    def test_not_found_on_empty_results(self) -> None:
        assert classify_failure([], "존재하지않는영화제목xyz") == FailureType.NOT_FOUND

    def test_year_ambiguity_on_duplicate_titles(self) -> None:
        # 동명이인/리메이크 케이스: top-10 내 같은 정규화 제목이 2개 이상
        duplicate = [
            {"original_title": "It", "title": "그것"},
            {"original_title": "It", "title": "그것"},
            {"original_title": "Other Movie", "title": "다른 영화"},
        ]
        assert classify_failure(duplicate, "It") == FailureType.YEAR_AMBIGUITY

    def test_title_mismatch_on_no_exact_match(self) -> None:
        # 결과는 있지만 정규화 비교에서 일치하는 항목이 없는 경우
        results = [
            {"original_title": "Inception", "title": "인셉션"},
            {"original_title": "Interstellar", "title": "인터스텔라"},
        ]
        assert classify_failure(results, "The Dark Knight") == FailureType.TITLE_MISMATCH


class TestCheckMatch:
    def test_top1_match(self) -> None:
        results = [
            {"id": 101, "original_title": "기생충", "title": "기생충"},
            {"id": 102, "original_title": "Other", "title": "다른"},
        ]
        entry = MovieEntry(language="ko", user_title="기생충")
        is_top1, is_top5, failure, top1_id = check_match(results, entry)

        assert is_top1 is True
        assert is_top5 is True
        assert failure is None
        assert top1_id == 101

    def test_top5_match_not_top1(self) -> None:
        # top-5 내에 있지만 첫 번째 결과가 아닌 경우
        results = [
            {"id": 201, "original_title": "Wrong Movie", "title": "틀린영화"},
            {"id": 202, "original_title": "Also Wrong", "title": "이것도 아님"},
            {"id": 203, "original_title": "Oldboy", "title": "올드보이"},
        ]
        entry = MovieEntry(language="ko", user_title="Oldboy")
        is_top1, is_top5, failure, top1_id = check_match(results, entry)

        assert is_top1 is False
        assert is_top5 is True
        assert failure is None
        assert top1_id == 201

    def test_no_match_returns_failure(self) -> None:
        results = [
            {"id": 301, "original_title": "Unrelated", "title": "관련없음"},
        ]
        entry = MovieEntry(language="en", user_title="NonExistentFilm")
        is_top1, is_top5, failure, top1_id = check_match(results, entry)

        assert is_top1 is False
        assert is_top5 is False
        assert failure == FailureType.TITLE_MISMATCH
        assert top1_id == 301


class TestBuildReport:
    def _make_results(self) -> list[MatchResult]:
        """10개 샘플 결과 픽스처: 한국 영화 6편, 외국 영화 4편."""
        return [
            # 한국 영화: top-1 명중 4편, top-5만 명중 1편, 실패 1편
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="ko", top1_tmdb_id=1, user_title="기생충"),
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="ko", top1_tmdb_id=2, user_title="올드보이"),
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="ko", top1_tmdb_id=3, user_title="부산행"),
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="ko", top1_tmdb_id=4, user_title="곡성"),
            MatchResult(failure_type=None, is_top1_match=False, is_top5_match=True, language="ko", top1_tmdb_id=5, user_title="밀정"),
            MatchResult(failure_type=FailureType.NOT_FOUND, is_top1_match=False, is_top5_match=False, language="ko", top1_tmdb_id=None, user_title="존재안함"),
            # 외국 영화: top-1 명중 2편, top-5만 명중 1편, 실패 1편
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="en", top1_tmdb_id=10, user_title="Inception"),
            MatchResult(failure_type=None, is_top1_match=True, is_top5_match=True, language="en", top1_tmdb_id=11, user_title="Interstellar"),
            MatchResult(failure_type=None, is_top1_match=False, is_top5_match=True, language="en", top1_tmdb_id=12, user_title="The Matrix"),
            MatchResult(failure_type=FailureType.TITLE_MISMATCH, is_top1_match=False, is_top5_match=False, language="en", top1_tmdb_id=13, user_title="Unknown Film"),
        ]

    def test_accuracy_calculation(self) -> None:
        results = self._make_results()
        report = build_report(results)

        # 전체 10편 중 top-1 명중 6편, top-5 명중 8편
        assert report["total"] == 10
        assert report["top1_hits"] == 6
        assert report["top5_hits"] == 8
        assert report["top1_accuracy"] == 0.6
        assert report["top5_accuracy"] == 0.8

    def test_korean_subset(self) -> None:
        results = self._make_results()
        report = build_report(results)

        # 한국 영화 6편: top-1 4편, top-5 5편
        korean = report["korean_subset"]
        assert korean["total"] == 6
        assert korean["top1_accuracy"] == round(4 / 6, 3)
        assert korean["top5_accuracy"] == round(5 / 6, 3)

    def test_foreign_subset(self) -> None:
        results = self._make_results()
        report = build_report(results)

        # 외국 영화 4편: top-1 2편, top-5 3편
        foreign = report["foreign_subset"]
        assert foreign["total"] == 4
        assert foreign["top1_accuracy"] == 0.5
        assert foreign["top5_accuracy"] == 0.75
