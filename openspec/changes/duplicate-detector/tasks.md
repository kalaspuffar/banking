## 1. Dedup Module Implementation

- [ ] 1.1 Create `bokforing/dedup.py` with the `filter_duplicates` function signature accepting `list[BankTransaction]` and `Path` to GnuCash book, returning `tuple[list[BankTransaction], list[BankTransaction]]`
- [ ] 1.2 Implement GnuCash book opening with `piecash.open_book(gnucash_book_path, readonly=True)` as a context manager
- [ ] 1.3 Extract all existing transaction `num` fields into a `set[str]`, filtering out empty/None values
- [ ] 1.4 Partition input transactions: iterate the input list and classify each transaction as new (Verifikationsnummer not in the set or empty) or duplicate (Verifikationsnummer found in the set)
- [ ] 1.5 Return the tuple of (new_transactions, duplicate_transactions) preserving input order

## 2. Tests

- [ ] 2.1 Create `tests/test_dedup.py` with a pytest fixture that programmatically creates a GnuCash SQLite book via piecash (with SEK currency, a bank account, and sample transactions with known `num` values)
- [ ] 2.2 Test: all new transactions against an empty book — expect all in new list, none in duplicates
- [ ] 2.3 Test: all duplicates — all input Verifikationsnummer already exist in book — expect none in new list, all in duplicates
- [ ] 2.4 Test: mixed scenario — some new, some duplicates — verify correct partitioning
- [ ] 2.5 Test: exact string match — "1001" vs "01001" are not duplicates
- [ ] 2.6 Test: empty Verifikationsnummer is always treated as new
- [ ] 2.7 Test: transaction order is preserved in both output lists
