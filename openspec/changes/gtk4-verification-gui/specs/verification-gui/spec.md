## ADDED Requirements

### Requirement: Display transactions in a table
The system SHALL display imported transactions in a `Gtk.ColumnView` with columns: Datum (booking_date), Text (transaction description), Belopp (amount in SEK), Konto (BAS account number), and Moms (VAT rate).

#### Scenario: All transactions visible after import
- **WHEN** the GTK4 application is launched with a list of 10 CategorizationSuggestion objects
- **THEN** the table displays 10 rows, each showing the transaction's datum, text, belopp, suggested konto, and moms rate

#### Scenario: Amounts formatted correctly
- **WHEN** a transaction has amount = Decimal("-125.00")
- **THEN** the Belopp column displays "-125,00" (Swedish decimal comma notation)

### Requirement: Show suggested accounts with visual indicators
The system SHALL display a filled square indicator for rows with a suggested account and a question mark indicator for rows without a suggestion.

#### Scenario: Categorized row shows filled square
- **WHEN** a CategorizationSuggestion has confidence "exact" or "pattern" and a debit_account assigned
- **THEN** the Konto column displays the indicator followed by the account number (e.g., "6540")

#### Scenario: Uncategorized row shows question mark
- **WHEN** a CategorizationSuggestion has confidence "none" and no account assigned
- **THEN** the Konto column displays "? ----" and the row is visually highlighted

### Requirement: Searchable account selector
The system SHALL provide a searchable account selector that filters BAS 2023 accounts by number or name as the user types.

#### Scenario: Filter by account number
- **WHEN** the user clicks the Konto cell of a row and types "193"
- **THEN** the selector list shows accounts matching "193" (e.g., "1930 - Foretagskonto")

#### Scenario: Filter by account name
- **WHEN** the user types "bank" in the account selector search field
- **THEN** the selector list shows accounts whose names contain "bank" (e.g., "6570 - Bankkostnader")

#### Scenario: Select account from list
- **WHEN** the user selects "6540 - IT-tjanster" from the filtered account list
- **THEN** the Konto column for that row updates to show "6540" and the row's indicator changes to the filled square

### Requirement: Accept or change categorizations
The system SHALL allow the user to accept a suggested categorization or change it to a different account for any row.

#### Scenario: Accept existing suggestion
- **WHEN** a row already has a suggested account and the user does not modify it
- **THEN** the suggestion is accepted as-is when saving

#### Scenario: Change suggested account
- **WHEN** the user selects a different account for a row that already had a suggestion
- **THEN** the row updates to show the new account and the new account is used when saving

### Requirement: Highlight uncategorized rows
The system SHALL visually highlight rows that do not yet have an account assigned, making them easy to identify.

#### Scenario: Uncategorized rows are visually distinct
- **WHEN** the table contains 4 categorized and 2 uncategorized transactions
- **THEN** the 2 uncategorized rows have a distinct background color or styling compared to categorized rows

### Requirement: Save button disabled until all categorized
The system SHALL disable the "Spara till GnuCash" button until every transaction in the table has an account assigned.

#### Scenario: Button disabled with uncategorized rows
- **WHEN** 2 out of 6 transactions are uncategorized
- **THEN** the "Spara till GnuCash" button is grayed out and not clickable

#### Scenario: Button enabled when all categorized
- **WHEN** the user assigns accounts to all remaining uncategorized rows
- **THEN** the "Spara till GnuCash" button becomes enabled

### Requirement: Save commits to GnuCash and updates rules
The system SHALL write all transactions to GnuCash via `gnucash_writer.write_transactions()` and persist new or updated categorization rules via `rules_db` when the user clicks "Spara till GnuCash".

#### Scenario: Successful save
- **WHEN** the user clicks "Spara till GnuCash" with all transactions categorized
- **THEN** all transactions are written to the GnuCash book, categorization rules are saved/updated in rules_db, and a success message is displayed

#### Scenario: Save error handling
- **WHEN** the GnuCash write fails (e.g., file locked)
- **THEN** an error dialog is shown with the error message, and no rules are updated

### Requirement: Running balance for reconciliation
The system SHALL display a running balance alongside each transaction so the user can reconcile against the bank's reported saldo.

#### Scenario: Running balance matches bank saldo
- **WHEN** transactions are displayed in date order
- **THEN** each row shows the bank's saldo value from the CSV, allowing the user to verify the running balance

### Requirement: Import summary display
The system SHALL display an import summary showing the count of new transactions, duplicates skipped, and any errors.

#### Scenario: Summary shown in status bar
- **WHEN** the application launches after processing 20 CSV rows where 15 are new and 5 are duplicates
- **THEN** the status area displays "15 nya transaktioner, 5 dubletter borttagna"

#### Scenario: Status bar shows categorization progress
- **WHEN** 10 of 15 new transactions have been categorized
- **THEN** the status bar shows "15 transaktioner, 10 kategoriserade, 5 kvar"
