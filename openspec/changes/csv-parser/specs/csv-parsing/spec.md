## ADDED Requirements

### Requirement: Parse bank CSV export
The system SHALL provide a function `parse_bank_csv(filepath: Path) -> list[BankTransaction]` that reads a semicolon-delimited, UTF-8 encoded CSV file and returns a list of BankTransaction objects ordered by booking_date.

#### Scenario: Successful parse of valid CSV
- **WHEN** `parse_bank_csv` is called with a valid bank CSV file containing 3 transactions
- **THEN** it returns a list of 3 BankTransaction objects sorted by booking_date ascending

#### Scenario: Empty CSV with only headers
- **WHEN** `parse_bank_csv` is called with a CSV file containing only the header row
- **THEN** it returns an empty list

### Requirement: Validate CSV header row
The system SHALL validate that the first row of the CSV contains exactly these column names: Bookkeepingsdatum, Valutadatum, Verifikationsnummer, Text, Belopp, Saldo.

#### Scenario: Invalid header raises CSVParseError
- **WHEN** `parse_bank_csv` is called with a CSV file whose header row has different column names
- **THEN** a CSVParseError is raised with a message describing the expected vs actual headers

### Requirement: Parse Swedish date format
The system SHALL parse date strings in YYYY-MM-DD format from the Bookkeepingsdatum and Valutadatum columns into Python `date` objects.

#### Scenario: Valid date parsing
- **WHEN** a row contains Bookkeepingsdatum "2026-01-28"
- **THEN** the BankTransaction has `booking_date = date(2026, 1, 28)`

#### Scenario: Invalid date raises CSVParseError
- **WHEN** a row contains an unparseable date like "28/01/2026"
- **THEN** a CSVParseError is raised mentioning the line number and the malformed value

### Requirement: Parse amounts with 3-decimal notation
The system SHALL parse amount strings from the Belopp and Saldo columns (e.g., `-125.000`, `10000.000`) into Decimal values quantized to 2 decimal places.

#### Scenario: Negative amount parsing
- **WHEN** a row contains Belopp "-125.000"
- **THEN** the BankTransaction has `amount = Decimal("-125.00")`

#### Scenario: Positive amount parsing
- **WHEN** a row contains Belopp "10000.000"
- **THEN** the BankTransaction has `amount = Decimal("10000.00")`

### Requirement: Reject malformed rows
The system SHALL raise CSVParseError with the line number when a row has missing fields, unparseable amounts, or unparseable dates.

#### Scenario: Missing field in row
- **WHEN** a CSV row has fewer columns than expected
- **THEN** a CSVParseError is raised with a message including the line number

#### Scenario: Unparseable amount
- **WHEN** a row contains Belopp "abc"
- **THEN** a CSVParseError is raised mentioning the line number and the invalid value

### Requirement: Test fixtures
The project SHALL include a test fixture file `tests/fixtures/sample_bank.csv` with representative bank transactions for testing.

#### Scenario: Fixture file is valid
- **WHEN** `parse_bank_csv` is called with the sample_bank.csv fixture
- **THEN** it parses successfully and returns the expected number of BankTransaction objects
