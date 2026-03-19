## Why

The import pipeline needs to ingest bank CSV exports as its first step. Without a parser, no transactions can enter the system. The bank exports semicolon-delimited CSVs with Swedish formatting conventions that require careful handling of dates, amounts (3-decimal notation), and UTF-8 encoding.

## What Changes

- Implement `bookkeeping/csv_parser.py` with `parse_bank_csv(filepath: Path) -> list[BankTransaction]`
- Parse semicolon-delimited CSV with columns: Bookkeepingsdatum, Valutadatum, Verifikationsnummer, Text, Belopp, Saldo
- Handle Swedish amount format (e.g., `-100.000` → `Decimal("-100.00")`)
- Validate header row and all required fields; raise `CSVParseError` with line numbers on failure
- Return transactions ordered by Bookkeepingsdatum
- Create comprehensive unit tests in `tests/test_csv_parser.py`
- Create test fixture `tests/fixtures/sample_bank.csv`

## Capabilities

### New Capabilities
- `csv-parsing`: Bank CSV file parsing with Swedish format handling, validation, and error reporting

### Modified Capabilities

## Impact

- **Code**: New module `bookkeeping/csv_parser.py` and test files
- **Dependencies**: Uses only Python stdlib (`csv`, `decimal`, `datetime`, `pathlib`)
- **Data**: Consumes bank CSV exports, produces `BankTransaction` objects (from models.py)
