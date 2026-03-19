## 1. Package Structure

- [x] 1.1 Create `pyproject.toml` with package metadata, Python ≥3.10 requirement, setuptools backend, runtime dependencies (piecash ≥1.2.0, weasyprint ≥60.0, Jinja2 ≥3.1), test dependencies (pytest ≥7.0), and `bookkeeping` console script entry point
- [x] 1.2 Create `bookkeeping/__init__.py` with package version string
- [x] 1.3 Create `bookkeeping/__main__.py` that delegates to `cli.main()` for `python -m bookkeeping` support

## 2. Data Models

- [x] 2.1 Create `bookkeeping/models.py` with custom exception hierarchy: `BookkeepingError`, `CSVParseError`, `GnuCashError`, `RulesDBError`
- [x] 2.2 Add frozen dataclass `BankTransaction` with all fields typed (date, Decimal, str)
- [x] 2.3 Add frozen dataclass `VATSplit` with `net_amount` and `vat_amount` (Decimal)
- [x] 2.4 Add frozen dataclass `CategorizationSuggestion` with transaction reference and account fields
- [x] 2.5 Add frozen dataclass `JournalEntrySplit` and `JournalEntry` (with splits list)
- [x] 2.6 Add mutable dataclass `Rule` with all fields for categorization rules
- [x] 2.7 Add frozen dataclass `CompanyInfo` for report headers
- [x] 2.8 Add frozen dataclass `ImportResult` with `transactions_written` and `errors`

## 3. CLI Stub

- [x] 3.1 Create `bookkeeping/cli.py` with a `main()` function stub that prints a usage message (full argparse logic deferred to Phase 4)

## 4. Test Infrastructure

- [x] 4.1 Create `tests/__init__.py`
- [x] 4.2 Create `tests/conftest.py` with fixtures: `sample_bank_transaction`, `sample_rule`, `sample_journal_entry`, `tmp_path` usage for temporary directories
- [x] 4.3 Create `tests/test_models.py` with tests for immutability of frozen dataclasses, Decimal precision, exception hierarchy, and Rule mutability
