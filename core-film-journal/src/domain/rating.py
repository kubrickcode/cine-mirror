"""평점 유효성 검증."""

from decimal import Decimal

_RATING_MIN = Decimal("0.0")
_RATING_MAX = Decimal("5.0")
_RATING_STEP = Decimal("0.5")


class InvalidRatingError(Exception):
    """유효하지 않은 평점."""

    def __init__(self, value: float) -> None:
        self.value = value
        super().__init__(
            f"평점 {value}은 유효하지 않습니다. "
            f"0.0~5.0 범위의 0.5 단위 숫자여야 합니다."
        )


def validate_rating(value: float | None) -> float | None:
    """평점을 검증하고 반환한다. None은 허용.

    Raises:
        InvalidRatingError: 범위 또는 단위 위반 시.
    """
    if value is None:
        return None

    decimal_value = Decimal(str(value))
    if decimal_value < _RATING_MIN or decimal_value > _RATING_MAX:
        raise InvalidRatingError(value)
    # 0.5 단위 검증: decimal_value를 RATING_STEP으로 나누었을 때 나머지가 없어야 함
    if decimal_value % _RATING_STEP != 0:
        raise InvalidRatingError(value)
    return value
