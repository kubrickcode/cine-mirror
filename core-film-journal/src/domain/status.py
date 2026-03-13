"""저널 상태 머신."""

# 허용된 상태 전이 맵. watched는 최종 상태 — 역방향 전이 불가.
_VALID_TRANSITIONS: dict[str, list[str]] = {
    "discovered": ["prioritized", "watched"],
    "prioritized": ["discovered", "watched"],
    "watched": [],
}


class InvalidTransitionError(Exception):
    """허용되지 않은 상태 전이 시도."""

    def __init__(self, from_status: str, to_status: str, allowed: list[str]) -> None:
        self.from_status = from_status
        self.to_status = to_status
        self.allowed = allowed
        super().__init__(
            f"'{from_status}'에서 '{to_status}'로 전이할 수 없습니다. "
            f"허용된 전이: {allowed}"
        )


class UnknownStatusError(Exception):
    """DB에 저장된 상태값이 상태 머신에 정의되지 않음."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"알 수 없는 상태값: '{status}'")


def get_allowed_transitions(status: str) -> list[str]:
    """현재 상태에서 허용된 전이 목록을 반환한다."""
    return list(_VALID_TRANSITIONS.get(status, []))


def transition_status(from_status: str, to_status: str) -> str:
    """상태 전이를 검증하고 새 상태를 반환한다.

    Raises:
        UnknownStatusError: from_status가 상태 머신에 없을 때.
        InvalidTransitionError: 허용되지 않은 전이일 때.
    """
    if from_status not in _VALID_TRANSITIONS:
        raise UnknownStatusError(from_status)
    allowed = _VALID_TRANSITIONS[from_status]
    if to_status not in allowed:
        raise InvalidTransitionError(from_status, to_status, allowed)
    return to_status
