## ADDED Requirements

### Requirement: BankTransaction dataclass
The system SHALL define a frozen dataclass `BankTransaction` with fields: `booking_date` (date), `value_date` (date), `verification_number` (str), `text` (str), `amount` (Decimal), `balance` (Decimal).

#### Scenario: BankTransaction is immutable
- **WHEN** code attempts to modify a field on a BankTransaction instance
- **THEN** a FrozenInstanceError is raised

#### Scenario: BankTransaction stores monetary values as Decimal
- **WHEN** a BankTransaction is created with `belopp=Decimal("-125.00")`
- **THEN** the `amount` field retains exact Decimal precision without float conversion

### Requirement: CategorizationSuggestion dataclass
The system SHALL define a frozen dataclass `CategorizationSuggestion` with fields: `transaction` (BankTransaction), `debit_account` (int), `credit_account` (int), `vat_rate` (Decimal), `vat_account` (int | None), `confidence` (str — one of "exact", "pattern", "none"), `rule_id` (int | None).

#### Scenario: CategorizationSuggestion references a BankTransaction
- **WHEN** a CategorizationSuggestion is created
- **THEN** its `transaction` field holds the originating BankTransaction

### Requirement: JournalEntry and JournalEntrySplit dataclasses
The system SHALL define frozen dataclasses `JournalEntrySplit` (fields: `account_code` int, `amount` Decimal) and `JournalEntry` (fields: `verification_number` str, `entry_date` date, `description` str, `splits` list[JournalEntrySplit]).

#### Scenario: JournalEntry splits sum to zero
- **WHEN** a JournalEntry is created with splits whose amounts sum to Decimal("0.00")
- **THEN** the entry represents a balanced double-entry transaction

#### Scenario: Positive split amount means debit
- **WHEN** a JournalEntrySplit has `amount=Decimal("100.00")`
- **THEN** it represents a debit of 100.00 SEK to the specified account

### Requirement: Rule dataclass
The system SHALL define a dataclass `Rule` with fields: `id` (int | None), `pattern` (str), `match_type` (str — "exact" or "contains"), `debit_account` (int), `credit_account` (int), `vat_rate` (Decimal), `vat_account` (int | None), `last_used` (date), `use_count` (int).

#### Scenario: Rule is mutable for database operations
- **WHEN** a Rule is loaded from the database and its `last_used` field is updated
- **THEN** the modification succeeds (Rule is not frozen)

### Requirement: CompanyInfo dataclass
The system SHALL define a frozen dataclass `CompanyInfo` with fields: `name` (str), `org_number` (str), `address` (str), `fiscal_year` (int).

#### Scenario: CompanyInfo is used for report headers
- **WHEN** a CompanyInfo is created with `name="Test AB"` and `org_number="123456-7890"`
- **THEN** both fields are accessible for rendering into report templates

### Requirement: ImportResult dataclass
The system SHALL define a frozen dataclass `ImportResult` with fields: `transactions_written` (int), `errors` (list[str]).

#### Scenario: ImportResult reports write outcome
- **WHEN** an import writes 5 transactions with no errors
- **THEN** ImportResult has `transactions_written=5` and `errors=[]`

### Requirement: VATSplit dataclass
The system SHALL define a frozen dataclass `VATSplit` with fields: `net_amount` (Decimal), `vat_amount` (Decimal).

#### Scenario: VATSplit holds calculated VAT components
- **WHEN** a VATSplit is created for a gross amount of -125.00 at 25% VAT
- **THEN** `net_amount` is Decimal("-100.00") and `vat_amount` is Decimal("-25.00")

### Requirement: Custom exception hierarchy
The system SHALL define a base exception `BookkeepingError(Exception)` and derived exceptions: `CSVParseError(BookkeepingError)`, `GnuCashError(BookkeepingError)`, `RulesDBError(BookkeepingError)`.

#### Scenario: CSVParseError is catchable as BookkeepingError
- **WHEN** code raises CSVParseError("Invalid row at line 5")
- **THEN** a `except BookkeepingError` handler catches it

#### Scenario: Exceptions carry descriptive messages
- **WHEN** CSVParseError is raised with a message describing the parsing failure
- **THEN** `str(error)` returns the descriptive message
