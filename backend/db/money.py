from decimal import Decimal

from db.errors import DbError


def require_fen(value: object, column: str, *, positive: bool) -> int:
    """Payments, refunds, and ledgers store integer fen. Floats are rejected."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DbError("INVALID_AMOUNT", f"{column} 必须是整数分")
    if positive and value <= 0:
        raise DbError("INVALID_AMOUNT", f"{column} 必须是正整数分")
    if value < 0:
        raise DbError("INVALID_AMOUNT", f"{column} 不能为负")
    return value


def require_decimal(value: object, column: str) -> Decimal | None:
    """Margin and USD amounts stay exact. Binary floats never land in numeric columns."""
    if value is None:
        return None
    if isinstance(value, (float, bool)):
        raise DbError("INVALID_AMOUNT", f"{column} 不能用二进制浮点")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception as exc:
            raise DbError("INVALID_AMOUNT", f"{column} 不是有效数字") from exc
    raise DbError("INVALID_AMOUNT", f"{column} 不是有效数字")
