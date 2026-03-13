"""평점 유효성 검증 단위 테스트."""

import pytest

from src.domain.rating import InvalidRatingError, validate_rating


class TestValidateRating:
    """평점 유효성 검증."""

    def test_none_allowed(self) -> None:
        """None은 허용 — 평점 없음 상태."""
        assert validate_rating(None) is None

    def test_zero_valid(self) -> None:
        """0.0은 유효한 최솟값."""
        assert validate_rating(0.0) == 0.0

    def test_half_step_valid(self) -> None:
        """0.5는 유효."""
        assert validate_rating(0.5) == 0.5

    def test_mid_valid(self) -> None:
        """2.5는 유효 (중간값)."""
        assert validate_rating(2.5) == 2.5

    def test_max_valid(self) -> None:
        """5.0은 유효한 최댓값."""
        assert validate_rating(5.0) == 5.0

    def test_non_half_step_invalid(self) -> None:
        """0.3은 0.5 단위가 아니므로 무효."""
        with pytest.raises(InvalidRatingError):
            validate_rating(0.3)

    def test_above_max_invalid(self) -> None:
        """5.5는 최댓값 초과."""
        with pytest.raises(InvalidRatingError):
            validate_rating(5.5)

    def test_negative_invalid(self) -> None:
        """-1은 음수이므로 무효."""
        with pytest.raises(InvalidRatingError):
            validate_rating(-1.0)

    def test_far_above_max_invalid(self) -> None:
        """6은 범위 초과."""
        with pytest.raises(InvalidRatingError):
            validate_rating(6.0)

    def test_invalid_rating_contains_value(self) -> None:
        """InvalidRatingError에 무효 값이 포함됨."""
        with pytest.raises(InvalidRatingError) as exc_info:
            validate_rating(0.3)
        assert exc_info.value.value == 0.3
