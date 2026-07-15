from __future__ import annotations

from app.schemas.common import MoneyAmount


def test_money_serializes_as_integer_minor_units_and_iso_currency() -> None:
    payload = MoneyAmount(amount_minor=117_000, currency_code="eur").model_dump(mode="json")

    assert payload == {"amount_minor": 117_000, "currency_code": "EUR"}
    assert isinstance(payload["amount_minor"], int)
