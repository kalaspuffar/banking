## Why

Confirmed, categorized transactions must be written into the user's GnuCash book as balanced double-entry transactions. This is the critical integration point where data flows from the tool into the user's existing accounting system. Without this module, the entire import pipeline has no output — parsed and categorized transactions would have nowhere to go.

The writer must be reliable above all else: it operates on the user's real financial data, so it must back up before writing, commit atomically (all-or-nothing), and fail clearly if something is wrong (locked book, missing account).

## What Changes

- Implement `bokforing/gnucash_writer.py` with `write_transactions(gnucash_book_path: Path, entries: list[JournalEntry]) -> ImportResult`
- Uses piecash to open the GnuCash SQLite book and create Transaction/Split objects
- Looks up BAS accounts by `code` field (the BAS account number stored in GnuCash)
- Stores Verifikationsnummer in the transaction `num` field for deduplication
- Creates automatic timestamped backup of the .gnucash file before any write
- Atomic commit: all transactions in a batch succeed or none are written
- Raises `GnuCashError` if the book is locked or a required account is not found
- Create comprehensive unit tests in `tests/test_gnucash_writer.py`

## Capabilities

### New Capabilities
- `gnucash-integration`: Write balanced double-entry transactions to a GnuCash SQLite book via piecash, with automatic backup and atomic commit

### Modified Capabilities

## Impact

- **Code**: New module `bokforing/gnucash_writer.py` and test file `tests/test_gnucash_writer.py`
- **Dependencies**: Requires `piecash>=1.2.0` (pip-installable, pure Python)
- **Data**: Writes to the user's GnuCash SQLite file — destructive operation mitigated by automatic backup
- **Interfaces**: Consumes `JournalEntry` objects (from models.py), produces `ImportResult` with counts and errors
