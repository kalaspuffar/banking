## Context

GnuCash uses a SQLite backend to store its double-entry accounting data. The piecash library provides Pythonic access to GnuCash books, handling the internal schema details (transactions, splits, commodities, accounts) and enforcing double-entry invariants. The writer module bridges the gap between the tool's internal JournalEntry model and GnuCash's data structures.

The user's GnuCash book already has the BAS 2023 chart of accounts set up with account codes (e.g., 1930, 3010, 2610). The writer looks up accounts by their `code` field, which stores the BAS number.

## Goals / Non-Goals

**Goals:**
- Write balanced double-entry transactions to the GnuCash book atomically (all-or-nothing)
- Automatically back up the .gnucash file before any write operation
- Store Verifikationsnummer in the transaction `num` field for duplicate detection
- Look up accounts by BAS code and raise clear errors if an account is not found
- Detect and report if the GnuCash book is locked (open in GnuCash GUI)

**Non-Goals:**
- Reading GnuCash data for reports (that is a separate `reports.py` module)
- Handling concurrent access with the GnuCash GUI (detect and error, do not attempt coordination)
- Creating or modifying the chart of accounts (accounts must already exist)
- Supporting GnuCash XML backend (SQLite only)

## Decisions

### 1. Use `piecash.open_book` as context manager
**Rationale**: piecash's context manager handles session lifecycle, commit, and cleanup. On exception the session rolls back automatically, giving us atomic behavior for free.
**Alternative considered**: Manual SQLAlchemy session management — unnecessarily complex and error-prone.

### 2. Look up accounts by `code` field (BAS number)
**Rationale**: The GnuCash `accounts.code` field stores the BAS account number (e.g., "1930"). This is a stable, unambiguous identifier. Account names may vary between setups but BAS codes are standardized.
**Alternative considered**: Lookup by name — fragile, may differ between GnuCash installations.

### 3. Amounts via Decimal; piecash handles value_num/value_denom
**Rationale**: piecash accepts Python Decimal values for split amounts and converts internally to the rational representation (value_num/value_denom). This avoids manual integer arithmetic and keeps the writer code clean.
**Alternative considered**: Setting value_num/value_denom directly — error-prone, no benefit.

### 4. Backup as `{book}.backup.{timestamp}` before write
**Rationale**: Simple file copy with shutil before opening the book for write. The timestamp format `YYYYMMDD-HHMMSS` ensures uniqueness and chronological sorting. This is a safety net against bugs or unexpected piecash behavior.
**Alternative considered**: Relying on GnuCash's built-in backup — not triggered by piecash writes; user may not have it configured.

### 5. SEK currency from `book.default_currency`
**Rationale**: The user's GnuCash book has SEK as its default currency. Using `book.default_currency` is cleaner than hard-coding a currency lookup. All transactions in this enskild firma are in SEK.
**Alternative considered**: Looking up SEK in `book.commodities` by mnemonic — works but adds unnecessary code when default_currency suffices.

## Risks / Trade-offs

- **[Risk] piecash write corrupts the GnuCash book** → Mitigation: Automatic backup before every write; extensive testing on programmatically created test books
- **[Risk] Account code not found in GnuCash** → Mitigation: Validate all account codes before creating any transactions; fail fast with a descriptive GnuCashError listing the missing code
- **[Risk] GnuCash GUI has the book open (SQLite lock)** → Mitigation: piecash raises an exception on open if the book is locked; catch and re-raise as GnuCashError with a user-friendly message
- **[Trade-off] Backup creates disk usage over time** → Acceptable: GnuCash files are small (KB); users can clean up old backups manually
