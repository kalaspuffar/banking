## ADDED Requirements

### Requirement: Filter duplicates from incoming transactions
The system SHALL provide a function `filter_duplicates(transactions: list[BankTransaction], gnucash_book_path: Path) -> tuple[list[BankTransaction], list[BankTransaction]]` that separates new transactions from those already present in the GnuCash book.

#### Scenario: All new transactions (empty book)
- **GIVEN** a GnuCash book with no existing transactions
- **WHEN** `filter_duplicates` is called with a list of 5 BankTransactions
- **THEN** it returns a tuple where the first list contains all 5 transactions and the second list is empty

#### Scenario: All duplicates (all already exist)
- **GIVEN** a GnuCash book containing transactions with `num` fields "1001", "1002", "1003"
- **WHEN** `filter_duplicates` is called with BankTransactions having Verifikationsnummer "1001", "1002", "1003"
- **THEN** it returns a tuple where the first list is empty and the second list contains all 3 transactions

#### Scenario: Mixed new and duplicate transactions
- **GIVEN** a GnuCash book containing transactions with `num` fields "1001", "1002"
- **WHEN** `filter_duplicates` is called with BankTransactions having Verifikationsnummer "1001", "1002", "1003", "1004"
- **THEN** the first list contains the 2 transactions with Verifikationsnummer "1003" and "1004"
- **AND** the second list contains the 2 transactions with Verifikationsnummer "1001" and "1002"

### Requirement: Match by exact string comparison
The system SHALL identify duplicates by exact string comparison between the BankTransaction's `verification_number` field and the GnuCash transaction's `num` field.

#### Scenario: Exact match required
- **GIVEN** a GnuCash book containing a transaction with `num` field "1001"
- **WHEN** `filter_duplicates` is called with a BankTransaction having Verifikationsnummer "01001"
- **THEN** the transaction is classified as new (not a duplicate), because "01001" != "1001"

### Requirement: Open GnuCash book in readonly mode
The system SHALL open the GnuCash book using piecash in readonly mode during duplicate detection, ensuring no modifications are made to the book.

#### Scenario: Book opened readonly
- **WHEN** `filter_duplicates` is called with a valid GnuCash book path
- **THEN** the book is opened with `piecash.open_book(path, readonly=True)`
- **AND** the book is not modified in any way

### Requirement: Handle transactions without Verifikationsnummer
The system SHALL treat transactions with an empty or missing Verifikationsnummer as new (never classified as duplicates).

#### Scenario: Empty Verifikationsnummer treated as new
- **GIVEN** a GnuCash book containing transactions with `num` fields "1001", "1002"
- **WHEN** `filter_duplicates` is called with a BankTransaction having an empty Verifikationsnummer ""
- **THEN** the transaction is classified as new (included in the first list)

### Requirement: Preserve transaction order
The system SHALL preserve the relative order of transactions within both the new and duplicate lists as they appeared in the input list.

#### Scenario: Order preserved in output
- **WHEN** `filter_duplicates` is called with transactions in a specific order
- **THEN** the new transactions list and the duplicate transactions list each maintain the same relative order as the input
