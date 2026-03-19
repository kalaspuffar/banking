## Why

Swedish VAT (moms) must be correctly split from gross amounts for all transactions. Every bank transaction that includes VAT needs to be decomposed into its net amount and VAT portion to produce correct double-entry bookkeeping splits. Without this, the categorization engine cannot generate balanced journal entries with VAT accounts, and downstream reports (momsdeklaration) will be incorrect.

## What Changes

- Implement `bokforing/vat.py` with `apply_vat_split(amount: Decimal, vat_rate: Decimal) -> VATSplit`
- Support the four Swedish VAT rates: 0%, 6%, 12%, 25%
- Use `Decimal` arithmetic throughout with `ROUND_HALF_EVEN` (banker's rounding) to ore precision
- Validate that the provided VAT rate is one of the allowed values; raise `ValueError` for unsupported rates
- VAT extraction formulas per Appendix C of the specification (e.g., 25%: vat = gross * 25/125)
- Create comprehensive unit tests in `tests/test_vat.py`

## Capabilities

### New Capabilities
- `vat-calculation`: VAT splitting from gross amounts using Swedish rates, with exact Decimal arithmetic and banker's rounding

### Modified Capabilities

## Impact

- **Code**: New module `bokforing/vat.py` and test file `tests/test_vat.py`
- **Dependencies**: Uses only Python stdlib (`decimal`). No external dependencies.
- **Data**: Consumes gross `Decimal` amounts, produces `VATSplit` named tuple / dataclass with `net_amount` and `vat_amount`
