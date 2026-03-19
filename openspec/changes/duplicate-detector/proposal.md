## Why

Importing overlapping date ranges from the bank's CSV export must not create duplicate entries in the GnuCash book. The bank assigns each transaction a unique Verifikationsnummer, which is stored in the GnuCash transaction's `num` field by the writer. Without a deduplication step, re-importing a CSV that overlaps with previously imported data would double-count transactions, corrupting the books.

## What Changes

- Implement `bokforing/dedup.py` with `filter_duplicates(transactions: list[BankTransaction], gnucash_book_path: Path) -> tuple[list[BankTransaction], list[BankTransaction]]`
- Use piecash to open the GnuCash book in readonly mode and query existing transaction `num` fields
- Partition incoming transactions into (new, duplicates) by exact string comparison of Verifikationsnummer against existing `num` values
- Create comprehensive unit tests in `tests/test_dedup.py` with programmatically created GnuCash test books via piecash

## Capabilities

### New Capabilities
- `duplicate-detection`: Detect and filter out previously imported transactions by comparing Verifikationsnummer against GnuCash book entries

### Modified Capabilities

## Impact

- **Code**: New module `bokforing/dedup.py` and test file `tests/test_dedup.py`
- **Dependencies**: Requires `piecash` for GnuCash book access and `bokforing.models` for BankTransaction
- **Data**: Reads GnuCash book (readonly); consumes list of BankTransaction, produces partitioned tuple of (new, duplicate) transactions
