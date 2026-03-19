## ADDED Requirements

### Requirement: Split VAT from gross amount at 25% rate
The system SHALL provide a function `apply_vat_split(amount: Decimal, vat_rate: Decimal) -> VATSplit` that extracts VAT from a gross amount using the formula `vat = amount * 25/125`.

#### Scenario: Expense with 25% VAT
- **WHEN** `apply_vat_split(Decimal("-125.00"), Decimal("25"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("-100.00")` and `vat_amount = Decimal("-25.00")`

#### Scenario: Income with 25% VAT
- **WHEN** `apply_vat_split(Decimal("10000.00"), Decimal("25"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("8000.00")` and `vat_amount = Decimal("2000.00")`

### Requirement: Split VAT from gross amount at 12% rate
The system SHALL extract VAT at 12% using the formula `vat = amount * 12/112`.

#### Scenario: Expense with 12% VAT
- **WHEN** `apply_vat_split(Decimal("-112.00"), Decimal("12"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("-100.00")` and `vat_amount = Decimal("-12.00")`

#### Scenario: Income with 12% VAT
- **WHEN** `apply_vat_split(Decimal("560.00"), Decimal("12"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("500.00")` and `vat_amount = Decimal("60.00")`

### Requirement: Split VAT from gross amount at 6% rate
The system SHALL extract VAT at 6% using the formula `vat = amount * 6/106`.

#### Scenario: Expense with 6% VAT
- **WHEN** `apply_vat_split(Decimal("-106.00"), Decimal("6"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("-100.00")` and `vat_amount = Decimal("-6.00")`

#### Scenario: Income with 6% VAT
- **WHEN** `apply_vat_split(Decimal("530.00"), Decimal("6"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("500.00")` and `vat_amount = Decimal("30.00")`

### Requirement: Handle 0% VAT rate
The system SHALL return the full amount as net and zero as VAT when the rate is 0%.

#### Scenario: Expense with 0% VAT
- **WHEN** `apply_vat_split(Decimal("-118.50"), Decimal("0"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("-118.50")` and `vat_amount = Decimal("0.00")`

#### Scenario: Income with 0% VAT
- **WHEN** `apply_vat_split(Decimal("500.00"), Decimal("0"))` is called
- **THEN** it returns a VATSplit with `net_amount = Decimal("500.00")` and `vat_amount = Decimal("0.00")`

### Requirement: Ore-level rounding with ROUND_HALF_EVEN
The system SHALL quantize VAT amounts to 2 decimal places using ROUND_HALF_EVEN (banker's rounding), and derive net as `gross - vat` to prevent rounding leakage.

#### Scenario: Rounding edge case with 25% VAT
- **WHEN** `apply_vat_split(Decimal("-99.99"), Decimal("25"))` is called
- **THEN** the `vat_amount` is quantized to 2 decimal places using ROUND_HALF_EVEN
- **AND** `net_amount + vat_amount == Decimal("-99.99")`

#### Scenario: Rounding edge case with 6% VAT
- **WHEN** `apply_vat_split(Decimal("-33.33"), Decimal("6"))` is called
- **THEN** the `vat_amount` is quantized to 2 decimal places using ROUND_HALF_EVEN
- **AND** `net_amount + vat_amount == Decimal("-33.33")`

#### Scenario: Small amount rounding
- **WHEN** `apply_vat_split(Decimal("-1.01"), Decimal("25"))` is called
- **THEN** `net_amount + vat_amount == Decimal("-1.01")`

### Requirement: Reject unsupported VAT rates
The system SHALL raise a ValueError when an unsupported VAT rate is provided. Supported rates are 0, 6, 12, and 25.

#### Scenario: Invalid VAT rate 10%
- **WHEN** `apply_vat_split(Decimal("-100.00"), Decimal("10"))` is called
- **THEN** a ValueError is raised with a message listing the supported rates

#### Scenario: Invalid VAT rate 21%
- **WHEN** `apply_vat_split(Decimal("-100.00"), Decimal("21"))` is called
- **THEN** a ValueError is raised

### Requirement: VATSplit invariant
For all valid inputs, the system SHALL guarantee that `vat_split.net_amount + vat_split.vat_amount == amount` (the original gross amount).

#### Scenario: Invariant holds for all rates and signs
- **GIVEN** any valid amount and any supported VAT rate
- **WHEN** `apply_vat_split(amount, rate)` is called
- **THEN** the returned `net_amount + vat_amount` equals the input `amount` exactly
