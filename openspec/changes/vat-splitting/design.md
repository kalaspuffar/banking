## Context

Bank transactions arrive as gross amounts that include VAT. Swedish bookkeeping requires every transaction to be split into its net amount and VAT portion so that the correct amounts are posted to expense/revenue accounts and VAT accounts (2610 Utgaende moms, 2640 Ingaende moms). The specification (Section 3.3 and Appendix C) defines the extraction formulas for each rate.

## Goals / Non-Goals

**Goals:**
- Exact Decimal arithmetic for all VAT calculations (no floating point)
- Support all four Swedish VAT rates: 0%, 6%, 12%, 25%
- Ore-level precision (2 decimal places) with ROUND_HALF_EVEN
- Ensure net + vat always equals the original gross amount (no rounding leakage)
- Clear error on unsupported VAT rates

**Non-Goals:**
- VAT reporting or aggregation (that belongs in the reports module)
- Determining which VAT rate applies to a transaction (that is the categorizer's job)
- Handling reverse charge VAT or EU cross-border VAT scenarios

## Decisions

### 1. Use Decimal throughout, never float
**Rationale**: Swedish bookkeeping requires ore-level accuracy. Floating point introduces representation errors that accumulate. Decimal provides exact decimal arithmetic.
**Alternative considered**: Integer ore arithmetic (amounts in ore as int) -- viable but less readable and the rest of the codebase uses Decimal.

### 2. ROUND_HALF_EVEN (banker's rounding)
**Rationale**: Standard for financial calculations. Eliminates systematic rounding bias. Specified in the project specification (Appendix C).

### 3. VAT extraction formulas from Appendix C
The formulas extract VAT from a gross (VAT-inclusive) amount:
- **25% VAT**: `vat = gross * 25/125`, `net = gross * 100/125`
- **12% VAT**: `vat = gross * 12/112`, `net = gross * 100/112`
- **6% VAT**: `vat = gross * 6/106`, `net = gross * 100/106`
- **0% VAT**: `vat = 0`, `net = gross`

Compute VAT first by multiplying by the rate fraction, quantize to 2 decimal places, then derive net as `gross - vat`. This ensures `net + vat == gross` exactly, avoiding rounding leakage.

### 4. Validate rate is one of the allowed values
**Rationale**: Accepting arbitrary rates could silently produce incorrect bookkeeping. The four rates are fixed by Swedish tax law. A ValueError for unsupported rates catches configuration or categorization errors early.

### 5. Define SUPPORTED_VAT_RATES as a module-level constant
**Rationale**: Single source of truth for valid rates. Used by both validation logic and tests. Defined as a frozenset of Decimal values: `{Decimal("0"), Decimal("6"), Decimal("12"), Decimal("25")}` (using percentage form for readability, with internal conversion to the fraction form for calculation).

## Risks / Trade-offs

- **[Risk] Rounding leakage** where `net + vat != gross` -> Mitigation: Compute vat first, then `net = gross - vat`, guaranteeing the invariant holds
- **[Trade-off] Percentage vs fraction representation of rates** -> Using percentage integers (25, 12, 6, 0) as the public API is more intuitive for Swedish users; internal conversion to fractions (25/125) is hidden
