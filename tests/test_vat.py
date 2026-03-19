"""Tests for the VAT splitting module.

Covers all four Swedish VAT rates (0%, 6%, 12%, 25%) with both positive
(income) and negative (expense) amounts, rounding edge cases, the
net+vat==gross invariant, and validation of unsupported rates.
"""

from decimal import Decimal

import pytest

from bookkeeping.vat import VATSplit, apply_vat_split


# ---------------------------------------------------------------------------
# 3.1  25% VAT rate — standard cases
# ---------------------------------------------------------------------------

class TestVATRate25:
    """Tests for the 25% VAT rate with standard amounts."""

    def test_expense_125(self) -> None:
        result = apply_vat_split(Decimal("-125.00"), Decimal("25"))
        assert result == VATSplit(
            net_amount=Decimal("-100.00"),
            vat_amount=Decimal("-25.00"),
        )

    def test_income_10000(self) -> None:
        result = apply_vat_split(Decimal("10000.00"), Decimal("25"))
        assert result == VATSplit(
            net_amount=Decimal("8000.00"),
            vat_amount=Decimal("2000.00"),
        )


# ---------------------------------------------------------------------------
# 3.2  12% VAT rate — standard cases
# ---------------------------------------------------------------------------

class TestVATRate12:
    """Tests for the 12% VAT rate with standard amounts."""

    def test_expense_112(self) -> None:
        result = apply_vat_split(Decimal("-112.00"), Decimal("12"))
        assert result == VATSplit(
            net_amount=Decimal("-100.00"),
            vat_amount=Decimal("-12.00"),
        )

    def test_income_560(self) -> None:
        result = apply_vat_split(Decimal("560.00"), Decimal("12"))
        assert result == VATSplit(
            net_amount=Decimal("500.00"),
            vat_amount=Decimal("60.00"),
        )


# ---------------------------------------------------------------------------
# 3.3  6% VAT rate — standard cases
# ---------------------------------------------------------------------------

class TestVATRate6:
    """Tests for the 6% VAT rate with standard amounts."""

    def test_expense_106(self) -> None:
        result = apply_vat_split(Decimal("-106.00"), Decimal("6"))
        assert result == VATSplit(
            net_amount=Decimal("-100.00"),
            vat_amount=Decimal("-6.00"),
        )

    def test_income_530(self) -> None:
        result = apply_vat_split(Decimal("530.00"), Decimal("6"))
        assert result == VATSplit(
            net_amount=Decimal("500.00"),
            vat_amount=Decimal("30.00"),
        )


# ---------------------------------------------------------------------------
# 3.4  0% VAT rate — full amount is net, VAT is zero
# ---------------------------------------------------------------------------

class TestVATRate0:
    """Tests for the 0% VAT rate (VAT-exempt transactions)."""

    def test_expense_zero_vat(self) -> None:
        result = apply_vat_split(Decimal("-118.50"), Decimal("0"))
        assert result == VATSplit(
            net_amount=Decimal("-118.50"),
            vat_amount=Decimal("0.00"),
        )

    def test_income_zero_vat(self) -> None:
        result = apply_vat_split(Decimal("500.00"), Decimal("0"))
        assert result == VATSplit(
            net_amount=Decimal("500.00"),
            vat_amount=Decimal("0.00"),
        )


# ---------------------------------------------------------------------------
# 4.1  Öre-level rounding edge cases
# ---------------------------------------------------------------------------

class TestRoundingEdgeCases:
    """Tests for amounts that produce repeating decimals when split."""

    def test_99_99_at_25_percent(self) -> None:
        """−99.99 at 25%: vat = −99.99 * 25/125 = −19.998 → −20.00 (ROUND_HALF_EVEN)."""
        result = apply_vat_split(Decimal("-99.99"), Decimal("25"))
        assert result.vat_amount == Decimal("-20.00")
        assert result.net_amount == Decimal("-79.99")

    def test_33_33_at_6_percent(self) -> None:
        """−33.33 at 6%: vat = −33.33 * 6/106 = −1.886792... → −1.89."""
        result = apply_vat_split(Decimal("-33.33"), Decimal("6"))
        assert result.vat_amount == Decimal("-1.89")
        assert result.net_amount == Decimal("-31.44")

    def test_1_01_at_25_percent(self) -> None:
        """−1.01 at 25%: vat = −1.01 * 25/125 = −0.202 → −0.20 (ROUND_HALF_EVEN)."""
        result = apply_vat_split(Decimal("-1.01"), Decimal("25"))
        assert result.vat_amount == Decimal("-0.20")
        assert result.net_amount == Decimal("-0.81")

    def test_positive_rounding_at_12_percent(self) -> None:
        """77.77 at 12%: vat = 77.77 * 12/112 = 8.331428... → 8.33."""
        result = apply_vat_split(Decimal("77.77"), Decimal("12"))
        assert result.vat_amount == Decimal("8.33")
        assert result.net_amount == Decimal("69.44")


# ---------------------------------------------------------------------------
# 4.2  net + vat == gross invariant
# ---------------------------------------------------------------------------

class TestInvariant:
    """The invariant net_amount + vat_amount == gross must always hold."""

    @pytest.mark.parametrize(
        "amount",
        [
            Decimal("-99.99"),
            Decimal("-33.33"),
            Decimal("-1.01"),
            Decimal("77.77"),
            Decimal("-0.01"),
            Decimal("999999.99"),
            Decimal("-12345.67"),
            Decimal("0.01"),
        ],
    )
    @pytest.mark.parametrize("rate", [Decimal("6"), Decimal("12"), Decimal("25")])
    def test_invariant_holds(self, amount: Decimal, rate: Decimal) -> None:
        result = apply_vat_split(amount, rate)
        assert result.net_amount + result.vat_amount == amount

    @pytest.mark.parametrize(
        "amount",
        [Decimal("-118.50"), Decimal("500.00"), Decimal("0.00")],
    )
    def test_invariant_holds_zero_rate(self, amount: Decimal) -> None:
        result = apply_vat_split(amount, Decimal("0"))
        assert result.net_amount + result.vat_amount == amount


# ---------------------------------------------------------------------------
# 4.3  Unsupported VAT rates raise ValueError
# ---------------------------------------------------------------------------

class TestUnsupportedRates:
    """Unsupported VAT rates must raise ValueError with a descriptive message."""

    def test_rate_10_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported VAT rate: 10"):
            apply_vat_split(Decimal("-100.00"), Decimal("10"))

    def test_rate_21_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported VAT rate: 21"):
            apply_vat_split(Decimal("-100.00"), Decimal("21"))

    def test_negative_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported VAT rate"):
            apply_vat_split(Decimal("-100.00"), Decimal("-5"))

    def test_message_lists_supported_rates(self) -> None:
        with pytest.raises(ValueError, match="Supported rates are: 0, 6, 12, 25"):
            apply_vat_split(Decimal("-100.00"), Decimal("99"))
