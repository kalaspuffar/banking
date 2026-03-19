## 1. Backup Function

- [ ] 1.1 Implement `_backup_book(gnucash_book_path: Path) -> Path` in `bokforing/gnucash_writer.py` that copies the book file to `{path}.backup.{YYYYMMDD-HHMMSS}` using `shutil.copy2` and returns the backup path
- [ ] 1.2 Add `GnuCashError` exception class to `bokforing/gnucash_writer.py` (or `bokforing/models.py` alongside other exceptions)

## 2. Account Lookup

- [ ] 2.1 Implement `_lookup_account(book, account_code: int)` that searches `book.accounts` for an account whose `code` field matches the given BAS number, raising `GnuCashError` if not found

## 3. Core Writer

- [ ] 3.1 Implement `write_transactions(gnucash_book_path: Path, entries: list[JournalEntry]) -> ImportResult` that:
  - Validates the book file exists, raising GnuCashError if not
  - Calls `_backup_book` to create a timestamped backup
  - Opens the book with `piecash.open_book(path, readonly=False)` as context manager
  - Resolves all account codes for all entries before creating any transactions (fail fast)
  - Creates piecash `Transaction` objects with `post_date`, `description`, `num` fields mapped from JournalEntry
  - Creates piecash `Split` objects for each JournalEntrySplit with correct account and amount
  - Uses `book.default_currency` for SEK currency
  - Commits via context manager exit (atomic)
  - Returns `ImportResult` with count of transactions written
- [ ] 3.2 Add error handling: catch piecash/SQLAlchemy lock exceptions and re-raise as `GnuCashError` with user-friendly message

## 4. Tests

- [ ] 4.1 Create `tests/test_gnucash_writer.py` with a pytest fixture that creates a test GnuCash book programmatically using piecash (with SEK currency and BAS accounts 1930, 3010, 2610, 2640, 6540)
- [ ] 4.2 Test: write a single 2-split transaction (bank + revenue) and verify it exists in the book with correct num, post_date, description, and split amounts
- [ ] 4.3 Test: write a 3-split transaction (bank + expense + VAT) and verify all splits are balanced
- [ ] 4.4 Test: write multiple transactions in one call and verify all are committed
- [ ] 4.5 Test: write with a non-existent account code raises GnuCashError and no transactions are written (atomic rollback)
- [ ] 4.6 Test: write to a non-existent book path raises GnuCashError
- [ ] 4.7 Test: backup file is created before writing and contains the original book data
