"""상태 머신 단위 테스트."""

import pytest

from src.domain.status import (
    InvalidTransitionError,
    UnknownStatusError,
    get_allowed_transitions,
    transition_status,
)


class TestTransitionStatus:
    """상태 전이 규칙."""

    def test_discovered_to_prioritized(self) -> None:
        """discovered → prioritized 전이 허용."""
        result = transition_status("discovered", "prioritized")
        assert result == "prioritized"

    def test_discovered_to_watched(self) -> None:
        """discovered → watched 직접 전이 허용."""
        result = transition_status("discovered", "watched")
        assert result == "watched"

    def test_prioritized_to_watched(self) -> None:
        """prioritized → watched 전이 허용."""
        result = transition_status("prioritized", "watched")
        assert result == "watched"

    def test_prioritized_to_discovered(self) -> None:
        """prioritized → discovered 역방향 전이 허용 (우선순위 취소)."""
        result = transition_status("prioritized", "discovered")
        assert result == "discovered"

    def test_watched_to_discovered_rejected(self) -> None:
        """watched → discovered 전이 거부 — 시청 완료 후 되돌릴 수 없음."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition_status("watched", "discovered")
        assert exc_info.value.from_status == "watched"
        assert exc_info.value.to_status == "discovered"
        assert exc_info.value.allowed == []

    def test_watched_to_prioritized_rejected(self) -> None:
        """watched → prioritized 전이 거부."""
        with pytest.raises(InvalidTransitionError):
            transition_status("watched", "prioritized")

    def test_same_status_transition_rejected(self) -> None:
        """동일 상태로의 전이 거부 — 전이 없음."""
        with pytest.raises(InvalidTransitionError):
            transition_status("discovered", "discovered")

    def test_allowed_list_in_error(self) -> None:
        """허용 전이 목록이 오류에 포함됨."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition_status("discovered", "invalid_status")
        assert "prioritized" in exc_info.value.allowed
        assert "watched" in exc_info.value.allowed

    def test_unknown_from_status_raises_unknown_error(self) -> None:
        """DB에 저장된 알 수 없는 상태값은 UnknownStatusError — 전이 불가와 구분됨."""
        with pytest.raises(UnknownStatusError) as exc_info:
            transition_status("corrupted_status", "watched")
        assert exc_info.value.status == "corrupted_status"


class TestGetAllowedTransitions:
    """허용 전이 목록 조회."""

    def test_discovered_has_two_transitions(self) -> None:
        assert set(get_allowed_transitions("discovered")) == {"prioritized", "watched"}

    def test_watched_has_no_transitions(self) -> None:
        assert get_allowed_transitions("watched") == []

    def test_unknown_status_returns_empty(self) -> None:
        """알 수 없는 상태는 빈 목록 — 방어적 처리."""
        assert get_allowed_transitions("unknown") == []
