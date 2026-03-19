## 1. VAT Module Setup

- [x] 1.1 Create `bookkeeping/vat.py` with module docstring explaining its purpose (VAT splitting for Swedish bookkeeping)
- [x] 1.2 Define `SUPPORTED_VAT_RATES` as a module-level frozenset: `{Decimal("0"), Decimal("6"), Decimal("12"), Decimal("25")}`
- [x] 1.3 Define `VATSplit` dataclass with fields `net_amount: Decimal` and `vat_amount: Decimal`

## 2. Core Implementation

- [x] 2.1 Implement `apply_vat_split(amount: Decimal, vat_rate: Decimal) -> VATSplit` with rate validation that raises `ValueError` for unsupported rates
- [x] 2.2 Implement VAT extraction using Decimal fraction arithmetic: `vat = amount * rate / (100 + rate)`, quantized to 2 decimal places with `ROUND_HALF_EVEN`
- [x] 2.3 Derive net amount as `net = amount - vat` to guarantee the invariant `net + vat == amount`
- [x] 2.4 Handle 0% rate as special case: return `VATSplit(net_amount=amount, vat_amount=Decimal("0.00"))`

## 3. Tests — Standard Cases

- [x] 3.1 Create `tests/test_vat.py` with tests for 25% VAT rate with both negative (expense) and positive (income) amounts
- [x] 3.2 Add tests for 12% VAT rate with both negative and positive amounts
- [x] 3.3 Add tests for 6% VAT rate with both negative and positive amounts
- [x] 3.4 Add tests for 0% VAT rate confirming full amount is net and vat is zero, for both signs

## 4. Tests — Edge Cases and Validation

- [x] 4.1 Add tests for ore-level rounding edge cases: amounts that produce repeating decimals when divided (e.g., -99.99 at 25%, -33.33 at 6%, -1.01 at 25%)
- [x] 4.2 Add tests verifying the `net + vat == gross` invariant holds for all edge case amounts
- [x] 4.3 Add tests that unsupported VAT rates (e.g., 10%, 21%, negative rates) raise ValueError with a descriptive message
