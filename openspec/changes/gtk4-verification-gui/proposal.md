## Why

Users need to review, confirm, and correct categorization suggestions before committing transactions to GnuCash. The categorization engine produces suggestions automatically, but the system's design principle is that no transaction is written without explicit user confirmation. A graphical interface provides the best user experience for this verification step — users can scan a table of transactions, see which ones are already categorized, fix the ones that aren't, and commit everything in one action.

Without this GUI, the user would need to confirm each transaction individually via CLI prompts, which is tedious for batches of 20-50 transactions at a time.

## What Changes

- Implement `bookkeeping/gtk_app.py` with a GTK4 application (`Gtk.Application` subclass)
- Transaction table with columns: Datum, Text, Belopp, Konto, Moms
- Searchable account selector using BAS 2023 chart of accounts
- Visual indicators for categorized rows (filled square) vs uncategorized rows (question mark)
- Import summary status bar showing counts: total, categorized, remaining
- "Spara till GnuCash" button enabled only when all transactions are categorized
- Running balance column for reconciliation against bank saldo
- On save: trigger `gnucash_writer.write_transactions()` and update rules via `rules_db`

## Capabilities

### New Capabilities
- `verification-gui`: GTK4 graphical interface for reviewing, editing, and confirming transaction categorizations before committing to GnuCash

### Modified Capabilities

## Impact

- **Code**: New module `bookkeeping/gtk_app.py` and basic test file `tests/test_gtk_app.py`
- **Dependencies**: Requires PyGObject and GTK4 system packages (`python3-gi`, `gir1.2-gtk-4.0`). These are system-level dependencies installed via apt, not pip.
- **Data**: Consumes `list[CategorizationSuggestion]` from the categorization engine; produces `list[JournalEntry]` for the GnuCash writer. Also triggers rule updates on save.
- **Integration**: Depends on Phase 1 modules: `categorizer`, `gnucash_writer`, `rules_db`, `models`
