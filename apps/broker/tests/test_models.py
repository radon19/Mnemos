from __future__ import annotations

from decimal import Decimal

import pytest

from mnemos_broker.models import YoctoAmount


def test_yocto_amount_keeps_u128_range_exact() -> None:
    column = YoctoAmount()
    assert column.process_bind_param(10**24, None) == Decimal(10**24)
    assert column.process_result_value(Decimal(10**24), None) == 10**24
    assert column.process_result_value(Decimal("0"), None) == 0


def test_yocto_amount_rejects_negative() -> None:
    with pytest.raises(ValueError):
        YoctoAmount().process_bind_param(-1, None)


def test_yocto_amount_passes_none_through() -> None:
    assert YoctoAmount().process_bind_param(None, None) is None
    assert YoctoAmount().process_result_value(None, None) is None
