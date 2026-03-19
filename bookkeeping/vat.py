"""VAT splitting for Swedish bookkeeping.

Splits gross (VAT-inclusive) transaction amounts into their net and VAT
components using the four Swedish VAT rates defined by Skatteverket.

All arithmetic uses ``decimal.Decimal`` with ``ROUND_HALF_EVEN`` (banker's
rounding) to guarantee öre-level accuracy. The invariant
``net_amount + vat_amount == gross_amount`` always holds because the VAT
portion is computed and quantized first, then the net portion is derived
by subtraction.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN


SUPPORTED_VAT_RATES: frozenset[Decimal] = frozenset({
    Decimal("0"),
    Decimal("6"),
    Decimal("12"),
    Decimal("25"),
})

_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class VATSplit:
    """Result of splitting a gross amount into net and VAT components.

    Attributes:
        net_amount: The amount excluding VAT.
        vat_amount: The VAT portion of the gross amount.
    """

    net_amount: Decimal
    vat_amount: Decimal


def apply_vat_split(amount: Decimal, vat_rate: Decimal) -> VATSplit:
    """Extract the VAT portion from a gross (VAT-inclusive) amount.

    Uses the extraction formula ``vat = amount * rate / (100 + rate)``
    and derives ``net = amount - vat`` to guarantee the invariant
    ``net + vat == amount``.

    Args:
        amount: The gross transaction amount (positive for income,
            negative for expenses).
        vat_rate: The VAT percentage as an integer-valued Decimal.
            Must be one of 0, 6, 12, or 25.

    Returns:
        A VATSplit with the net and VAT components.

    Raises:
        ValueError: If vat_rate is not one of the supported Swedish
            VAT rates (0, 6, 12, 25).
    """
    if vat_rate not in SUPPORTED_VAT_RATES:
        supported = ", ".join(str(r) for r in sorted(SUPPORTED_VAT_RATES))
        raise ValueError(
            f"Unsupported VAT rate: {vat_rate}%. "
            f"Supported rates are: {supported}%"
        )

    if vat_rate == Decimal("0"):
        return VATSplit(
            net_amount=amount,
            vat_amount=Decimal("0.00"),
        )

    # VAT extraction: vat = amount * rate / (100 + rate)
    # e.g. for 25%: vat = amount * 25 / 125
    vat_amount = (amount * vat_rate / (Decimal("100") + vat_rate)).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_EVEN
    )
    net_amount = amount - vat_amount

    return VATSplit(net_amount=net_amount, vat_amount=vat_amount)
