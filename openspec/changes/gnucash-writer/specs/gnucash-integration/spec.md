## ADDED Requirements

### Requirement: Write balanced transactions to GnuCash
The system SHALL provide a function `write_transactions(gnucash_book_path: Path, entries: list[JournalEntry]) -> ImportResult` that writes balanced double-entry transactions to the GnuCash SQLite book via piecash.

#### Scenario: Successful write of a single transaction
- **WHEN** `write_transactions` is called with a valid GnuCash book path and a list containing one JournalEntry with two splits that sum to zero
- **THEN** the transaction is written to the GnuCash book and ImportResult reports 1 transaction written with no errors

#### Scenario: Successful write of multiple transactions
- **WHEN** `write_transactions` is called with 3 valid JournalEntry objects
- **THEN** all 3 transactions are written to the GnuCash book and ImportResult reports 3 transactions written

#### Scenario: Transaction with VAT split (3 splits)
- **WHEN** `write_transactions` is called with a JournalEntry containing 3 splits (bank, expense, VAT) that sum to zero
- **THEN** a GnuCash transaction with 3 splits is created, each split assigned to the correct account

### Requirement: Store Verifikationsnummer in num field
The system SHALL store the JournalEntry's `verifikationsnummer` in the GnuCash transaction's `num` field, the `datum` in `post_date`, and the `beskrivning` in `description`.

#### Scenario: Verifikationsnummer persisted
- **WHEN** a JournalEntry with verifikationsnummer "12345678" is written
- **THEN** the resulting GnuCash transaction has `num = "12345678"`

#### Scenario: Transaction description and date persisted
- **WHEN** a JournalEntry with datum 2026-01-28 and beskrivning "Spotify" is written
- **THEN** the GnuCash transaction has `post_date = date(2026, 1, 28)` and `description = "Spotify"`

### Requirement: Automatic backup before writing
The system SHALL create a backup copy of the GnuCash file before writing any transactions. The backup SHALL be named `{book_path}.backup.{YYYYMMDD-HHMMSS}`.

#### Scenario: Backup file created
- **WHEN** `write_transactions` is called with book path `/home/user/book.gnucash`
- **THEN** a file `/home/user/book.gnucash.backup.{timestamp}` exists before any transactions are written

#### Scenario: Backup is a faithful copy
- **WHEN** a backup is created before writing
- **THEN** the backup file content is identical to the original book file at the time of backup

### Requirement: Atomic commit (all or nothing)
The system SHALL write all transactions in a single atomic commit. If any transaction fails (e.g., invalid account code), none of the transactions in the batch SHALL be written.

#### Scenario: Rollback on failure
- **WHEN** `write_transactions` is called with 3 entries where the 2nd entry references a non-existent account code
- **THEN** a GnuCashError is raised and none of the 3 transactions are present in the GnuCash book

#### Scenario: Successful atomic commit
- **WHEN** `write_transactions` is called with 3 valid entries
- **THEN** all 3 are committed in a single operation and are all present in the GnuCash book afterward

### Requirement: Account lookup by BAS code
The system SHALL look up GnuCash accounts by the `code` field, which contains the BAS 2023 account number (e.g., "1930", "3010").

#### Scenario: Account found by code
- **WHEN** a JournalEntrySplit references account_code 1930 and the GnuCash book has an account with code "1930"
- **THEN** the split is assigned to that account

#### Scenario: Account not found
- **WHEN** a JournalEntrySplit references account_code 9999 and no GnuCash account has code "9999"
- **THEN** a GnuCashError is raised with a message indicating that account code 9999 was not found

### Requirement: GnuCashError on locked or inaccessible book
The system SHALL raise a GnuCashError if the GnuCash book file is locked (e.g., open in GnuCash GUI) or if the file does not exist.

#### Scenario: Book locked by GnuCash GUI
- **WHEN** `write_transactions` is called and the book file is locked
- **THEN** a GnuCashError is raised with a message indicating the book is locked

#### Scenario: Book file does not exist
- **WHEN** `write_transactions` is called with a non-existent book path
- **THEN** a GnuCashError is raised with a message indicating the file was not found
