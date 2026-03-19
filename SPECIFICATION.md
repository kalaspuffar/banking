# Project Specification: Swedish Bookkeeping Automation for Enskild Firma

**Version**: 1.0
**Date**: 2026-03-19
**Author**: Solution Architect (Claude)
**Status**: Draft

---

## 1. Executive Summary

### Project Overview
Build a set of Python helper tools around the user's existing GnuCash installation to automate the bookkeeping workflow for a Swedish enskild firma. The tools handle CSV import from the bank, rule-based transaction categorization with VAT splitting, user verification via a lightweight GTK4 interface, and PDF report generation for momsdeklaration, NE-bilaga, grundbok, and huvudbok.

### Key Objectives
1. **Eliminate manual data entry** — bank CSV transactions flow into GnuCash programmatically
2. **Learn categorization patterns** — recurring transactions are auto-suggested after first categorization
3. **Preserve user control** — all suggestions require confirmation in a GUI before committing
4. **Generate tax-ready reports** — PDF outputs mapped directly to Skatteverket form fields

### Success Criteria
- 100% of bank transactions importable without manual entry
- 90%+ auto-suggestion accuracy for recurring transactions after initial training
- Zero duplicates when importing overlapping date ranges
- PDF reports contain all values needed for momsdeklaration and NE-bilaga
- Full workflow completable by the proprietor on Debian/Ubuntu Linux

---

## 2. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Workflow                      │
│                                                      │
│  bank CSV ──► Import ──► Categorize ──► Verify ──►  │
│               Tool       Engine        (GTK4)       │
│                                           │          │
│                                     ┌─────▼──────┐  │
│                                     │  GnuCash    │  │
│                                     │  (SQLite)   │  │
│                                     └─────┬──────┘  │
│                                           │          │
│                                     ┌─────▼──────┐  │
│                                     │   Report    │  │
│                                     │  Generator  │  │
│                                     └─────┬──────┘  │
│                                           │          │
│                                      PDF Reports    │
└─────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        bookkeeping/                           │
│                                                              │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  csv_parser  │──►│ categorizer   │──►│ gnucash_writer  │  │
│  │             │   │              │   │   (piecash)      │  │
│  └─────────────┘   └──────┬───────┘   └────────┬────────┘  │
│                           │                     │            │
│                    ┌──────▼───────┐       ┌─────▼────────┐  │
│                    │  rules_db    │       │  GnuCash     │  │
│                    │  (SQLite)    │       │  book.gnucash│  │
│                    └──────────────┘       └─────┬────────┘  │
│                                                 │            │
│  ┌─────────────┐   ┌──────────────┐            │            │
│  │  gtk_app    │──►│ report_gen   │◄───────────┘            │
│  │  (GTK4)     │   │ (WeasyPrint) │                         │
│  └─────────────┘   └──────────────┘                         │
└──────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Core bookkeeping engine | GnuCash (existing instance) | User already has it set up with BAS 2023; proven double-entry system |
| GnuCash integration | piecash (Python library) | Pure Python, pip-installable, enforces double-entry invariants, well-documented |
| Categorization rules storage | Separate SQLite database | Decoupled from GnuCash data; survives GnuCash upgrades; easily backed up |
| GUI framework | GTK4 via PyGObject | Native Linux toolkit; available in Debian repos; user preference |
| PDF generation | WeasyPrint (HTML/CSS → PDF) | Templates are easy to maintain; good A4 layout support |
| Programming language | Python 3 | piecash is Python; rich ecosystem; maintainable by single developer |
| CLI framework | argparse (stdlib) | No extra dependency; sufficient for this tool's needs |

---

## 3. System Components

### 3.1 CSV Parser (`bookkeeping.csv_parser`)

**Purpose**: Parse the bank's semicolon-delimited CSV export into structured transaction objects.

**Responsibilities**:
- Read UTF-8 CSV files with semicolon delimiter
- Parse Swedish date format (YYYY-MM-DD)
- Parse amounts with 3 decimal places (e.g., `-100.000` → `-100.00` SEK)
- Validate all required fields are present
- Return a list of `BankTransaction` objects

**Interface**:
```python
def parse_bank_csv(filepath: Path) -> list[BankTransaction]:
    """Parse a bank CSV export file.

    Raises:
        CSVParseError: If the file format is invalid or fields are missing.

    Returns:
        List of BankTransaction objects, ordered by booking_date.
    """
```

**Implementation Notes**:
- Use Python's `csv` module with `delimiter=';'`
- Amount parsing: strip trailing zero from 3-decimal format, convert to `Decimal`
- Validate header row matches expected column names
- Reject files with missing or malformed rows (report line number in error)

**Traceability**: F-IMP-01, F-IMP-02, F-IMP-03

---

### 3.2 Duplicate Detector (`bookkeeping.dedup`)

**Purpose**: Prevent the same transaction from being imported twice by checking Verifikationsnummer against existing GnuCash entries.

**Responsibilities**:
- Query existing transactions in the GnuCash book
- Compare incoming transactions by Verifikationsnummer
- Filter out duplicates, returning only new transactions
- Report the count of duplicates skipped

**Interface**:
```python
def filter_duplicates(
    transactions: list[BankTransaction],
    gnucash_book_path: Path
) -> tuple[list[BankTransaction], list[BankTransaction]]:
    """Separate new transactions from duplicates.

    Returns:
        Tuple of (new_transactions, duplicate_transactions).
    """
```

**Implementation Notes**:
- Use piecash to open the GnuCash book in readonly mode
- The bank's verification number is stored in the GnuCash transaction's `num` field
- Match is exact string comparison on `num`
- This check runs before any categorization to avoid wasted effort

**Traceability**: F-IMP-04, F-IMP-05, BR-06

---

### 3.3 Categorization Engine (`bookkeeping.categorizer`)

**Purpose**: Suggest BAS 2023 account mappings for transactions based on stored rules, and handle VAT splitting.

**Responsibilities**:
- Match transaction text against stored categorization rules
- Suggest debit/credit account pairs with VAT rate
- Generate the split structure for double-entry (including VAT splits)
- Store new/updated rules when the user confirms or corrects a categorization
- Never auto-commit — always return suggestions for user confirmation

**Interface**:
```python
def suggest_categorization(
    transaction: BankTransaction,
    rules_db: RulesDatabase
) -> CategorSuggestion | None:
    """Suggest account mapping for a transaction.

    Returns:
        A CategorSuggestion with accounts and VAT info, or None if no match.
    """

def apply_vat_split(
    amount: Decimal,
    vat_rate: Decimal
) -> VATSplit:
    """Calculate net amount and VAT portion.

    For amount=-125.00 with vat_rate=0.25:
      net = -100.00, vat = -25.00

    Returns:
        VATSplit with net_amount and vat_amount.
    """

def save_rule(
    rules_db: RulesDatabase,
    pattern: str,
    debit_account: int,
    credit_account: int,
    vat_rate: Decimal
) -> None:
    """Save or update a categorization rule."""
```

**Pattern Matching Logic**:
1. Exact match on the full transaction `Text` field (highest priority)
2. Prefix/contains match on a normalized version of the text (lowercase, stripped of date suffixes like `/26-01-23`)
3. If multiple rules match, use the one with the most recent `last_used` date

**VAT Splitting Logic**:
For a transaction with VAT, the double-entry splits are:

*Example: Consulting invoice received, 10,000 SEK including 25% moms*
| Split | Account | Debit | Credit |
|---|---|---|---|
| Bank | 1930 Företagskonto | 10,000 | |
| Revenue | 3010 Försäljning tjänster 25% | | 8,000 |
| VAT | 2610 Utgående moms 25% | | 2,000 |

*Example: Software subscription expense, -125 SEK including 25% moms*
| Split | Account | Debit | Credit |
|---|---|---|---|
| Bank | 1930 Företagskonto | | 125 |
| Expense | 6212 Programvarulicenser | 100 | |
| VAT | 2640 Ingående moms | 25 | |

*Example: YouTube revenue, 500 SEK, no Swedish VAT*
| Split | Account | Debit | Credit |
|---|---|---|---|
| Bank | 1930 Företagskonto | 500 | |
| Revenue | 3040 Försäljning tjänster momsfri | | 500 |

**Traceability**: F-CAT-01 through F-CAT-07, BR-01, BR-02, BR-03

---

### 3.4 Rules Database (`bookkeeping.rules_db`)

**Purpose**: Persist categorization rules in a dedicated SQLite database, separate from GnuCash.

**Responsibilities**:
- CRUD operations on categorization rules
- Pattern-based lookup for suggestions
- Track last-used timestamp for rule ranking
- Export/import rules for backup

**Interface**:
```python
class RulesDatabase:
    def __init__(self, db_path: Path): ...
    def find_rule(self, transaction_text: str) -> Rule | None: ...
    def save_rule(self, rule: Rule) -> None: ...
    def update_last_used(self, rule_id: int) -> None: ...
    def list_rules(self) -> list[Rule]: ...
    def delete_rule(self, rule_id: int) -> None: ...
    def export_rules(self, filepath: Path) -> None: ...
    def import_rules(self, filepath: Path) -> None: ...
```

**Traceability**: F-CAT-03, F-CAT-05, NF-REL-03

---

### 3.5 GnuCash Writer (`bookkeeping.gnucash_writer`)

**Purpose**: Write confirmed, categorized transactions into the GnuCash book via piecash.

**Responsibilities**:
- Open GnuCash SQLite book file
- Look up BAS accounts by account code
- Create balanced transactions with correct splits
- Store verification_number in the transaction `num` field for deduplication
- Commit atomically — all transactions in a batch succeed or none do

**Interface**:
```python
def write_transactions(
    gnucash_book_path: Path,
    entries: list[JournalEntry]
) -> ImportResult:
    """Write journal entries to the GnuCash book.

    Opens the book with piecash, creates Transaction/Split objects,
    and saves. Atomic: all-or-nothing commit.

    Returns:
        ImportResult with count of transactions written and any errors.
    """
```

**Implementation Notes**:
- Use `piecash.open_book(path, readonly=False)` as context manager
- Look up accounts using `book.accounts` filtered by `code` field (the BAS account number)
- Amounts stored as rational numbers: `value_num` = amount in öre, `value_denom` = 100
- The `currency` for all transactions is SEK (from `book.default_currency` or looked up in commodities)
- Transaction `post_date` = booking_date from CSV
- Transaction `description` = text from CSV
- Transaction `num` = verification_number from CSV
- **Always back up the .gnucash file before writing** (the tool should create a timestamped copy)
- GnuCash must NOT be open simultaneously (SQLite locking)

**Traceability**: F-IMP-01, I-GC-01, I-GC-02, I-GC-03, NF-REL-02, BR-01

---

### 3.6 GTK4 Verification Application (`bookkeeping.gtk_app`)

**Purpose**: Provide a graphical interface for the user to review, confirm, and correct categorization suggestions before committing to GnuCash.

**Responsibilities**:
- Display imported transactions in a table view
- Show suggested BAS account for each transaction (or highlight as uncategorized)
- Allow the user to accept, change, or override categorizations
- Provide searchable account selection (dropdown/combobox with account number + description)
- Show import summary (new, duplicates skipped, errors)
- Trigger the write to GnuCash on user confirmation
- Show running balance for reconciliation against bank balance

**Window Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  Bokföring - Import & Kategorisering                     │
├──────────────────────────────────────────────────────────┤
│  [Öppna CSV...]  [GnuCash-fil: /path/to/book.gnucash]   │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Datum     │ Text        │ Belopp  │ Konto   │ Moms │  │
│  ├───────────┼─────────────┼─────────┼─────────┼──────┤  │
│  │ 2026-01-28│ Spotify     │ -125.00 │ ■ 6540  │ 25%  │  │
│  │ 2026-01-26│ Google AdS..│ +500.00 │ ■ 3040  │  0%  │  │
│  │ 2026-01-14│ Bankavgift  │ -118.50 │ ? ----  │  0%  │  │
│  │ ...       │             │         │         │      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Status: 6 transaktioner, 4 kategoriserade, 2 kvar      │
│                                                          │
│  [Spara till GnuCash]                    [Avbryt]        │
└──────────────────────────────────────────────────────────┘
```

**Key Interactions**:
- Clicking a row opens account selection for that transaction
- Account selector shows searchable list: `1930 - Företagskonto`, `3010 - Försäljning tjänster 25%`, etc.
- Pre-categorized rows (from rules) shown with ■ marker
- Uncategorized rows shown with ? marker and highlighted
- User can only click "Spara till GnuCash" when all transactions are categorized
- After saving, updated/new categorization rules are persisted automatically

**Implementation Notes**:
- GTK4 via PyGObject (`gi.repository.Gtk` version 4.0)
- Use `Gtk.ColumnView` or `Gtk.TreeView` for the transaction table
- Account selector: `Gtk.SearchEntry` + `Gtk.ListView` filtered by typed text
- Run in a single window; no multi-window complexity

**Traceability**: F-GUI-01 through F-GUI-07, NF-USE-01, NF-USE-02

---

### 3.7 Report Generator (`bookkeeping.reports`)

**Purpose**: Read transaction data from the GnuCash book and generate PDF reports for tax filing and legal archiving.

**Responsibilities**:
- Query GnuCash SQLite for transactions within a fiscal year
- Aggregate amounts by BAS account
- Map aggregated values to Skatteverket form fields
- Render HTML templates with Jinja2
- Convert HTML to A4 PDF via WeasyPrint

**Reports Produced**:

#### 3.7.1 Momsdeklaration Summary

Maps account totals to the SKV 4700 form fields:

| Ruta | Description | Source |
|---|---|---|
| 05 | Momspliktig försäljning (25%) | Sum of account 3010 (net of VAT) |
| 06 | Momspliktig försäljning (12%) | Sum of account 3011 (if used) |
| 07 | Momspliktig försäljning (6%) | Sum of account 3012 (if used) |
| 08 | Momsfri försäljning | Sum of account 3040 |
| 10 | Utgående moms (25%) | Sum of account 2610 |
| 11 | Utgående moms (12%) | Sum of account 2620 (if used) |
| 12 | Utgående moms (6%) | Sum of account 2630 (if used) |
| 48 | Ingående moms | Sum of account 2640 |
| 49 | Moms att betala/få tillbaka | Ruta 10+11+12 - Ruta 48 |

*Note: Exact ruta numbers must be validated against current Skatteverket SKV 4700 form. The above is based on the standard simplified yearly VAT return.*

#### 3.7.2 NE-bilaga Summary

Maps account totals to the NE form (INK1 bilaga) fields:

| Ruta | Description | Source |
|---|---|---|
| R1 | Nettoomsättning | Sum of accounts 30xx |
| R2 | Övriga rörelseintäkter | Sum of accounts 37xx-39xx |
| R5 | Övriga externa kostnader | Sum of accounts 50xx-69xx |
| R6 | Övriga rörelsekostnader | Sum of accounts 79xx |
| R7 | Bokfört resultat | R1+R2-R5-R6 (simplified) |
| B1 | Eget kapital vid årets början | Account 2010 opening balance |
| B4 | Eget kapital vid årets slut | Account 2010 closing balance |

*Note: Exact ruta numbers must be validated against current Skatteverket INK1 NE form. This is a simplified mapping for a small enskild firma.*

#### 3.7.3 Grundbok (Journal)

Chronological listing of all transactions for the fiscal year:

| Column | Content |
|---|---|
| Verifikation | Verifikationsnummer |
| Datum | Bokföringsdatum |
| Text | Transaction description |
| Konto | BAS account number + name |
| Debet | Debit amount |
| Kredit | Credit amount |

Sorted by date, then by Verifikationsnummer. Includes page totals and grand totals.

#### 3.7.4 Huvudbok (General Ledger)

Transactions grouped by BAS account:

For each account with activity:
- Account number and name as header
- Opening balance
- All transactions (date, verifikation, text, debit, credit)
- Closing balance

Sorted by account number. Includes account subtotals.

**PDF Template Structure**:
Each report is an HTML/CSS template in `bookkeeping/templates/`:
- `momsdeklaration.html` — VAT summary
- `ne_bilaga.html` — NE attachment summary
- `grundbok.html` — Journal
- `huvudbok.html` — General ledger
- `base.html` — Shared layout (A4, headers, page numbers, company info)

**Interface**:
```python
def generate_report(
    report_type: str,  # "moms", "ne", "grundbok", "huvudbok"
    gnucash_book_path: Path,
    fiscal_year: int,
    output_path: Path,
    company_info: CompanyInfo
) -> Path:
    """Generate a PDF report for the given fiscal year.

    Returns:
        Path to the generated PDF file.
    """
```

**Traceability**: F-RPT-01 through F-RPT-08, I-PDF-01, I-PDF-02, I-PDF-03, BR-04

---

## 4. Data Architecture

### 4.1 Data Models

#### BankTransaction (parsed from CSV)
```python
@dataclass(frozen=True)
class BankTransaction:
    booking_date: date          # Booking date (CSV: Bokföringsdatum)
    value_date: date            # Value date (CSV: Valutadatum)
    verification_number: str    # Unique transaction ID from bank (CSV: Verifikationsnummer)
    text: str                   # Transaction description (CSV: Text)
    amount: Decimal             # Amount in SEK, negative=expense, positive=income (CSV: Belopp)
    balance: Decimal            # Running balance after transaction (CSV: Saldo)
```

#### CategorizationSuggestion (from categorization engine)
```python
@dataclass(frozen=True)
class CategorizationSuggestion:
    transaction: BankTransaction
    debit_account: int          # BAS account number (e.g., 1930)
    credit_account: int         # BAS account number (e.g., 3010)
    vat_rate: Decimal           # 0.00, 0.06, 0.12, or 0.25
    vat_account: int | None     # BAS VAT account (e.g., 2610) or None if 0%
    confidence: Confidence      # "exact", "pattern", or "none"
    rule_id: int | None         # ID of the matching rule, if any
```

#### JournalEntry (ready to write to GnuCash)
```python
@dataclass(frozen=True)
class JournalEntrySplit:
    account_code: int           # BAS account number
    amount: Decimal             # Positive = debit, negative = credit

@dataclass(frozen=True)
class JournalEntry:
    verification_number: str
    entry_date: date
    description: str
    splits: tuple[JournalEntrySplit, ...]  # Must sum to zero (enforced at construction)
```

#### Rule (categorization rule)
```python
@dataclass
class Rule:
    id: int | None
    pattern: str                # Text pattern to match
    match_type: MatchType       # "exact" or "contains" (validated at construction)
    debit_account: int          # BAS account number
    credit_account: int         # BAS account number
    vat_rate: Decimal
    vat_account: int | None
    last_used: date
    use_count: int
```

#### CompanyInfo (for report headers)
```python
@dataclass(frozen=True)
class CompanyInfo:
    name: str                   # Company/proprietor name
    org_number: str             # Organisationsnummer
    address: str
    fiscal_year: int
```

### 4.2 Database Schema — Rules Database

File: `~/.local/share/bookkeeping/rules.db`

```sql
CREATE TABLE rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern         TEXT NOT NULL,
    match_type      TEXT NOT NULL DEFAULT 'contains',  -- 'exact' or 'contains'
    debit_account   INTEGER NOT NULL,
    credit_account  INTEGER NOT NULL,
    vat_rate        TEXT NOT NULL DEFAULT '0.00',       -- stored as text for precision
    vat_account     INTEGER,
    last_used       TEXT NOT NULL,                      -- ISO 8601 date
    use_count       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(pattern, match_type)
);

CREATE INDEX idx_rules_pattern ON rules(pattern);
CREATE INDEX idx_rules_last_used ON rules(last_used DESC);

CREATE TABLE config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
-- Stores: gnucash_book_path, company_name, org_number, etc.

CREATE TABLE import_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    import_date         TEXT NOT NULL DEFAULT (datetime('now')),
    csv_filename        TEXT NOT NULL,
    transactions_total  INTEGER NOT NULL,
    transactions_new    INTEGER NOT NULL,
    transactions_dup    INTEGER NOT NULL,
    transactions_error  INTEGER NOT NULL
);
```

### 4.3 GnuCash Data Mapping

The tool reads/writes to the user's existing GnuCash SQLite book. Key mappings:

| Our Field | GnuCash Table | GnuCash Field |
|---|---|---|
| verification_number | transactions | num |
| booking_date | transactions | post_date |
| text (description) | transactions | description |
| BAS account code | accounts | code |
| Split amount | splits | value_num / value_denom |
| Currency (SEK) | commodities | mnemonic = 'SEK' |

**Amount encoding**: piecash handles the rational number conversion. A Decimal amount of `125.50` becomes `value_num=12550, value_denom=100`.

### 4.4 Data Volume and Retention

- ~200-400 transactions/year → trivial for SQLite
- Rules database: ~50-100 rules for a small business
- GnuCash book: grows by ~5-10 KB/month
- PDF reports: ~10-20 pages/year, archived for 7 years per bokföringslagen
- Automatic backup of .gnucash file before every write operation

---

## 5. API Specifications (CLI Interface)

The tool is invoked via a single CLI entry point: `bookkeeping`

### 5.1 `bookkeeping import <csv_file>`

**Description**: Parse a bank CSV, detect duplicates, launch the GTK4 categorization GUI, and write confirmed transactions to GnuCash.

**Arguments**:
| Argument | Required | Description |
|---|---|---|
| `csv_file` | Yes | Path to the bank CSV export |
| `--book` | No | Path to GnuCash file (default: from config) |
| `--dry-run` | No | Parse and categorize but don't write to GnuCash |
| `--no-gui` | No | CLI-only mode: show suggestions, require manual confirmation |

**Flow**:
1. Parse CSV → `list[BankTransaction]`
2. Open GnuCash book (readonly) → filter duplicates
3. Apply categorization rules → `list[CategorizationSuggestion]`
4. Launch GTK4 GUI for verification
5. On user confirmation → write to GnuCash, update rules
6. Print import summary

**Exit codes**: 0 = success, 1 = parse error, 2 = GnuCash error, 3 = user cancelled

### 5.2 `bookkeeping report <type> <year>`

**Description**: Generate a PDF report from GnuCash data.

**Arguments**:
| Argument | Required | Description |
|---|---|---|
| `type` | Yes | One of: `moms`, `ne`, `grundbok`, `huvudbok`, `all` |
| `year` | Yes | Fiscal year (e.g., `2025`) |
| `--book` | No | Path to GnuCash file (default: from config) |
| `--output-dir` | No | Directory for PDF output (default: `./rapporter/`) |

**Output**: PDF file(s) named `{type}_{year}.pdf` (e.g., `momsdeklaration_2025.pdf`)

### 5.3 `bookkeeping rules`

**Description**: Manage categorization rules.

**Subcommands**:
| Subcommand | Description |
|---|---|
| `rules list` | Show all stored rules |
| `rules delete <id>` | Delete a rule by ID |
| `rules export <file>` | Export rules to JSON |
| `rules import <file>` | Import rules from JSON |

### 5.4 `bookkeeping config`

**Description**: View and set configuration.

**Subcommands**:
| Subcommand | Description |
|---|---|
| `config show` | Display current configuration |
| `config set <key> <value>` | Set a config value |

**Config keys**: `gnucash_book_path`, `company_name`, `org_number`, `company_address`

### 5.5 `bookkeeping init`

**Description**: First-time setup wizard. Creates the rules database, prompts for GnuCash book path and company info.

---

## 6. Security Architecture

### Data Protection
- All data stored locally in `~/.local/share/bookkeeping/` (rules DB, config) and the user's GnuCash file
- No network communication whatsoever (NF-SEC-01, NF-SEC-02)
- File permissions: rules.db created with `0600` (owner read/write only) (NF-SEC-03)

### Backup Strategy
- Before every write to GnuCash: create `{book}.backup.{timestamp}` copy
- Rules DB backup: `bookkeeping rules export` produces portable JSON
- PDF reports are self-contained archival documents

### Input Validation
- CSV parser validates all fields and rejects malformed input
- Amount parsing uses `Decimal` (never float) to avoid rounding errors
- Account codes validated against the GnuCash book's actual chart of accounts
- All user input in GTK4 GUI constrained to valid account selections

---

## 7. Infrastructure and Deployment

### System Requirements
- **OS**: Debian 12+ / Ubuntu 22.04+ (any Debian-based Linux)
- **GnuCash**: 4.x or 5.x with SQLite backend
- **Python**: 3.10+

### Dependencies

**System packages** (apt):
```
gnucash
python3
python3-pip
python3-gi
python3-gi-cairo
gir1.2-gtk-4.0
libgirepository-1.0-dev
```

**Python packages** (pip):
```
piecash>=1.2.0
weasyprint>=60.0
Jinja2>=3.1
```

### Installation
```bash
# System dependencies
sudo apt install gnucash python3-gi gir1.2-gtk-4.0

# Python package (from project directory)
pip install --user -e .

# First-time setup
bookkeeping init
```

### Project Structure
```
bookkeeping/
├── pyproject.toml              # Package metadata and dependencies
├── README.md                   # User documentation
├── bookkeeping/
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point
│   ├── cli.py                  # argparse CLI definitions
│   ├── csv_parser.py           # Bank CSV parsing
│   ├── dedup.py                # Duplicate detection
│   ├── categorizer.py          # Rule-based categorization engine
│   ├── rules_db.py             # SQLite rules database
│   ├── gnucash_writer.py       # piecash integration
│   ├── reports.py              # Report data aggregation
│   ├── gtk_app.py              # GTK4 verification GUI
│   ├── models.py               # Data classes
│   ├── config.py               # Configuration management
│   ├── vat.py                  # VAT splitting logic
│   └── templates/
│       ├── base.html           # Shared PDF layout
│       ├── momsdeklaration.html
│       ├── ne_bilaga.html
│       ├── grundbok.html
│       └── huvudbok.html
└── tests/
    ├── test_csv_parser.py
    ├── test_dedup.py
    ├── test_categorizer.py
    ├── test_vat.py
    ├── test_gnucash_writer.py
    ├── test_reports.py
    └── fixtures/
        ├── sample_bank.csv
        └── test_book.gnucash
```

---

## 8. Integration Points

### 8.1 GnuCash (via piecash)
- **Read**: Account lookup, duplicate checking, report data queries
- **Write**: Transaction creation with balanced splits
- **Constraint**: GnuCash GUI must not be open while the tool writes (SQLite single-writer lock)
- **Backup**: Automatic timestamped backup before every write

### 8.2 Bank CSV Export
- **Format**: Semicolon-delimited, UTF-8, Swedish dates and amounts
- **Interface**: User manually exports from online banking and provides file path
- **Resilience**: Parser is isolated so format changes only affect `csv_parser.py`

### 8.3 Skatteverket Forms (reference only)
- No direct integration — PDF reports are designed for manual transcription
- Form field references (ruta numbers) embedded in report templates
- Templates must be updated if Skatteverket changes form layout

### 8.4 SRU File Generation (Future Phase)
- Architecture supports adding an `sru_generator.py` module alongside `reports.py`
- Uses the same GnuCash data queries; outputs plain-text SRU format instead of PDF
- Not implemented in Phase 1

---

## 9. Testing Strategy

### Unit Tests
- **csv_parser**: Valid CSV, malformed rows, encoding issues, amount edge cases (3 decimal places, negative zero)
- **dedup**: Matching and non-matching Verifikationsnummer, empty book, partial overlap
- **categorizer**: Exact match, contains match, no match, multiple matches (priority), VAT splitting
- **vat**: All four VAT rates (0%, 6%, 12%, 25%), öre-level precision, rounding
- **rules_db**: CRUD operations, pattern uniqueness, last_used ordering
- **gnucash_writer**: Balanced transactions, account lookup, atomic commit/rollback

### Integration Tests
- **Full import pipeline**: CSV → parse → dedup → categorize → write → verify in GnuCash book
- **Report generation**: Write known transactions → generate each report → verify totals
- **Round-trip**: Import transactions, generate grundbok, verify every transaction appears

### Acceptance Tests
- Process the sample `account.csv` through the full workflow
- Compare one quarter of real data against the volunteer's reports
- Values must match to the öre

### Test Framework
- **pytest** with fixtures for test GnuCash books and sample CSVs
- Test GnuCash books created programmatically via piecash in fixtures

---

## 10. Implementation Plan

### Phase 1: Core Import Pipeline (MVP)
**Components**: csv_parser, models, dedup, categorizer, rules_db, gnucash_writer, vat
**Acceptance Criteria**:
- [ ] Parse `account.csv` into structured data
- [ ] Detect and skip duplicates against GnuCash book
- [ ] Match transactions to rules and suggest accounts
- [ ] Split VAT correctly for 25% and 0% rates
- [ ] Write balanced transactions to GnuCash via piecash
- [ ] Create automatic backup before writing
- [ ] All unit tests pass

**Estimated Effort**: Core functionality, highest priority

### Phase 2: GTK4 Verification GUI
**Components**: gtk_app
**Acceptance Criteria**:
- [ ] Display imported transactions in a table
- [ ] Show suggested accounts with visual indicators
- [ ] Searchable account selector dropdown
- [ ] Accept/change categorizations per transaction
- [ ] Highlight uncategorized transactions
- [ ] "Save to GnuCash" button commits and updates rules
- [ ] Running balance shown for reconciliation

**Dependencies**: Phase 1 complete

### Phase 3: PDF Report Generation
**Components**: reports, templates/
**Acceptance Criteria**:
- [ ] Momsdeklaration PDF with ruta references
- [ ] NE-bilaga PDF with ruta references
- [ ] Grundbok PDF (chronological journal)
- [ ] Huvudbok PDF (per-account ledger)
- [ ] All reports on A4 with headers, page numbers, company info
- [ ] Totals verified against GnuCash balances

**Dependencies**: Phase 1 complete (can run in parallel with Phase 2)

### Phase 4: CLI, Config, and Polish
**Components**: cli, config, init wizard, error handling
**Acceptance Criteria**:
- [ ] `bookkeeping init` sets up the environment
- [ ] `bookkeeping import` runs the full pipeline
- [ ] `bookkeeping report` generates all report types
- [ ] `bookkeeping rules` manages categorization rules
- [ ] Clear error messages for all failure modes
- [ ] Import log tracking

**Dependencies**: Phases 1-3 complete

### Phase 5 (Future): SRU File Generation
**Components**: sru_generator
- Not part of initial delivery
- Architecture accommodates it without changes to other components

---

## 11. Risks and Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | piecash writes corrupt the GnuCash book | Low | Critical | Automatic backup before every write; test extensively on scratch books |
| R-02 | GnuCash SQLite schema changes between versions | Low | High | Pin piecash version; test on upgrade; piecash maintainers track schema changes |
| R-03 | Concurrent GnuCash GUI access during write | Medium | High | Check for lock file before writing; clear error message if locked |
| R-04 | Skatteverket form field numbers are incorrect | Medium | Medium | Validate against actual forms during Phase 3; make ruta mappings configurable in templates |
| R-05 | BAS account codes in GnuCash don't match expected format | Low | Medium | Validate account lookup during init; report missing accounts clearly |
| R-06 | VAT splitting produces öre rounding errors | Low | Medium | Use `Decimal` everywhere; explicit rounding rules (banker's rounding); test edge cases |
| R-07 | GTK4 availability varies across distros | Low | Low | GTK4 is standard on modern Debian/Ubuntu; fallback: CLI-only mode |
| R-08 | WeasyPrint rendering differences | Low | Low | Pin version; test PDF output visually |

---

## 12. Appendices

### A. Glossary

See REQUIREMENTS.md Appendix A for the full Swedish-English glossary.

### B. BAS 2023 Account Mapping for This Business

| Account | Name | Usage | VAT |
|---|---|---|---|
| 1930 | Företagskonto / checkkonto | Bank account (all transactions) | — |
| 2010 | Eget kapital | Owner's equity | — |
| 2610 | Utgående moms 25% | Output VAT on consulting | — |
| 2640 | Ingående moms | Input VAT on purchases | — |
| 2650 | Momsredovisningskonto | VAT settlement | — |
| 3010 | Försäljning tjänster, 25% moms | Consulting revenue | 25% |
| 3040 | Försäljning tjänster, momsfri | YouTube revenue | 0% |
| 6212 | Programvarulicenser | Software subscriptions | 25% |
| 6540 | IT-tjänster | IT services | 25% |
| 6570 | Bankkostnader | Bank fees | 0% |
| 8300 | Ränteintäkter | Interest income | 0% |

### C. VAT Calculation Reference

**Extracting VAT from a gross amount** (when the transaction amount includes VAT):
```
For 25% VAT:  vat = gross_amount × 25/125 = gross_amount × 0.20
              net = gross_amount × 100/125 = gross_amount × 0.80

For 12% VAT:  vat = gross_amount × 12/112
              net = gross_amount × 100/112

For 6% VAT:   vat = gross_amount × 6/106
              net = gross_amount × 100/106
```

All calculations use `Decimal` with `ROUND_HALF_EVEN` (banker's rounding) to öre precision.

### D. Momsdeklaration Field Reference (SKV 4700)

*To be validated against current Skatteverket form during Phase 3 implementation.*

The simplified yearly VAT return (förenklad årsmomsdeklaration) for small businesses typically includes:

- **Ruta 05**: Momspliktig försäljning 25% (taxable sales)
- **Ruta 06**: Momspliktig försäljning 12%
- **Ruta 07**: Momspliktig försäljning 6%
- **Ruta 08**: Momsfri försäljning (VAT-exempt sales)
- **Ruta 10**: Utgående moms 25%
- **Ruta 11**: Utgående moms 12%
- **Ruta 12**: Utgående moms 6%
- **Ruta 48**: Ingående moms att dra av
- **Ruta 49**: Moms att betala eller få tillbaka

### E. NE-bilaga Field Reference (INK1)

*To be validated against current Skatteverket form during Phase 3 implementation.*

Key fields in the NE-bilaga for resultaträkning (income statement) and balansräkning (balance sheet):

- **R1**: Nettoomsättning (net revenue)
- **R2**: Övriga rörelseintäkter
- **R5**: Övriga externa kostnader
- **R6**: Övriga rörelsekostnader
- **R7**: Bokfört resultat (book profit/loss)
- **B1**: Eget kapital vid årets början
- **B4**: Eget kapital vid årets slut

### F. Technology Stack Summary

| Component | Technology | Version | Source |
|---|---|---|---|
| Bookkeeping engine | GnuCash | 4.x / 5.x | apt |
| GnuCash integration | piecash | ≥1.2.0 | pip |
| Language | Python | ≥3.10 | apt |
| GUI | GTK4 / PyGObject | 4.x | apt |
| PDF generation | WeasyPrint | ≥60.0 | pip |
| Templating | Jinja2 | ≥3.1 | pip |
| Database | SQLite3 | (stdlib) | Python stdlib |
| Testing | pytest | ≥7.0 | pip |
