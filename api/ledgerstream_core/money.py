from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def d2(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
