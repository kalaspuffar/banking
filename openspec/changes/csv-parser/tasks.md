## 1. Test Fixtures

- [ ] 1.1 Create `tests/fixtures/` directory and `tests/fixtures/sample_bank.csv` with 5-6 representative transactions (mix of income, expenses, bank fees) using the exact bank CSV format from `account.csv`

## 2. CSV Parser Implementation

- [ ] 2.1 Create `bokforing/csv_parser.py` with the expected CSV column names as constants
- [ ] 2.2 Implement header validation that raises CSVParseError on mismatch
- [ ] 2.3 Implement date parsing (YYYY-MM-DD → date) with CSVParseError on failure
- [ ] 2.4 Implement amount parsing (3-decimal string → Decimal quantized to 2 places) with CSVParseError on failure
- [ ] 2.5 Implement `parse_bank_csv(filepath: Path) -> list[BankTransaction]` tying it all together, returning transactions sorted by bokforingsdatum

## 3. Tests

- [ ] 3.1 Create `tests/test_csv_parser.py` with tests for: valid CSV parsing, empty CSV, invalid headers, malformed dates, malformed amounts, missing fields, sorting by date
- [ ] 3.2 Add edge case tests: UTF-8 Swedish characters in Text field, negative zero amount, very large amounts
