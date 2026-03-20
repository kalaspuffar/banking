# Bookkeeping — Swedish Bookkeeping Automation for GnuCash

A Python toolchain that automates the bookkeeping workflow for a Swedish *enskild firma* (sole proprietorship). It bridges the gap between bank CSV exports and GnuCash, handling transaction import, rule-based categorization with VAT splitting, user verification via a GTK4 GUI, and PDF report generation for Swedish tax forms.

## Features

- **Bank CSV import** — Parse semicolon-delimited bank exports with Swedish date and amount formats
- **Duplicate detection** — Prevent double-importing by checking verification numbers against the GnuCash book
- **Rule-based categorization** — Auto-suggest BAS 2023 account mappings for recurring transactions, with learning from user corrections
- **VAT splitting** — Automatically split transactions into net amount and VAT (25%, 12%, 6%, or 0%) across the correct accounts
- **GTK4 verification GUI** — Review, accept, or override suggested categorizations before committing
- **PDF report generation** — Produce tax-ready reports mapped to Skatteverket form fields:
  - **Momsdeklaration** (VAT return, SKV 4700)
  - **NE-bilaga** (income tax attachment, INK1)
  - **Grundbok** (chronological journal)
  - **Huvudbok** (general ledger by account)

## Architecture

```
bank CSV ──► CSV Parser ──► Dedup ──► Categorizer ──► GTK4 GUI ──► GnuCash
                                          │                           │
                                     Rules DB                    Report Gen
                                     (SQLite)                        │
                                                                PDF Reports
```

| Component           | Module                    | Purpose                                    |
|---------------------|---------------------------|--------------------------------------------|
| CSV Parser          | `bookkeeping.csv_parser`  | Parse bank export into structured data      |
| Duplicate Detector  | `bookkeeping.dedup`       | Filter already-imported transactions        |
| Categorizer         | `bookkeeping.categorizer` | Match transactions to BAS accounts via rules|
| VAT Splitter        | `bookkeeping.vat`         | Calculate net/VAT split for each rate       |
| Rules Database      | `bookkeeping.rules_db`    | Persist categorization rules (SQLite)       |
| GnuCash Writer      | `bookkeeping.gnucash_writer` | Write balanced entries via piecash        |
| GTK4 GUI            | `bookkeeping.gtk_app`     | Visual verification and account selection   |
| Report Generator    | `bookkeeping.reports`     | Aggregate data and render PDF via WeasyPrint|
| CLI                 | `bookkeeping.cli`         | argparse-based command-line interface        |

## Requirements

### System

- **OS**: Debian 12+ / Ubuntu 22.04+ (or any Debian-based Linux)
- **Python**: 3.10+
- **GnuCash**: 4.x or 5.x with SQLite backend

### System packages

```bash
sudo apt install gnucash python3-gi gir1.2-gtk-4.0 python3-gi-cairo libgirepository-1.0-dev
```

### Python packages

Installed automatically via pip:
- `piecash` — GnuCash SQLite integration
- `weasyprint` — HTML/CSS to PDF conversion
- `Jinja2` — Report template rendering

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd bookkeeping

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package in development mode
pip install -e ".[dev]"

# Run first-time setup
bookkeeping init
```

## Usage

### First-time setup

```bash
bookkeeping init
```

Prompts for your GnuCash book path, company name, organisationsnummer, and address. Configuration is stored in `~/.local/share/bookkeeping/rules.db`.

### Import bank transactions

```bash
# Full GUI mode (default)
bookkeeping import account.csv

# CLI-only mode
bookkeeping import account.csv --no-gui

# Preview without writing
bookkeeping import account.csv --dry-run

# Specify GnuCash book explicitly
bookkeeping import account.csv --book /path/to/book.gnucash
```

### Generate reports

```bash
# Single report
bookkeeping report vat 2025
bookkeeping report ne 2025
bookkeeping report journal 2025
bookkeeping report ledger 2025

# All reports at once
bookkeeping report all 2025

# Custom output directory
bookkeeping report all 2025 --output-dir ./reports/
```

### Manage categorization rules

```bash
bookkeeping rules list
bookkeeping rules delete 5
bookkeeping rules export backup.json
bookkeeping rules import backup.json
```

### View and set configuration

```bash
bookkeeping config show
bookkeeping config set company_name "My Company"
bookkeeping config set gnucash_book_path /path/to/book.gnucash
```

## Report Types

| CLI name   | Swedish name       | Description                              | Tax form    |
|------------|--------------------|------------------------------------------|-------------|
| `vat`      | Momsdeklaration    | VAT return with box (ruta) values        | SKV 4700    |
| `ne`       | NE-bilaga          | Income tax attachment for sole proprietor | INK1        |
| `journal`  | Grundbok           | Chronological journal of all entries      | —           |
| `ledger`   | Huvudbok           | General ledger grouped by account         | —           |

## Domain Context

This project operates in the Swedish accounting domain:

- **BAS 2023** — The standard Swedish chart of accounts (kontoplan). Account numbers like 1930 (bank), 3010 (sales), 2610 (output VAT) follow this standard.
- **Skatteverket forms** — Reports map directly to fields (rutor) on Swedish tax authority forms.
- **Double-entry bookkeeping** — All transactions are balanced with debit and credit splits, enforced by GnuCash via piecash.

### Code language convention

All Python code uses **English** identifiers. Swedish appears only in domain-specific contexts: CSV column headers from the bank, BAS account names, tax form field descriptions, and UI labels in the GTK4 interface.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests cover CSV parsing, duplicate detection, categorization rules, VAT splitting, GnuCash integration, report generation (including PDF output validation), CLI argument parsing, and GTK4 widget logic.

## Project Structure

```
bookkeeping/
├── pyproject.toml
├── README.md
├── bookkeeping/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # CLI entry point and subcommands
│   ├── config.py               # Configuration management
│   ├── csv_parser.py           # Bank CSV parsing
│   ├── categorizer.py          # Rule-based categorization engine
│   ├── dedup.py                # Duplicate detection
│   ├── gnucash_writer.py       # GnuCash integration via piecash
│   ├── gtk_app.py              # GTK4 verification GUI
│   ├── journal.py              # Journal entry construction
│   ├── models.py               # Data classes and types
│   ├── reports.py              # Report data aggregation and PDF generation
│   ├── rules_db.py             # SQLite rules database
│   ├── vat.py                  # VAT splitting logic
│   └── templates/
│       ├── base.html           # Shared PDF layout (A4, headers, page numbers)
│       ├── momsdeklaration.html
│       ├── ne_bilaga.html
│       ├── grundbok.html
│       └── huvudbok.html
└── tests/
    ├── test_categorizer.py
    ├── test_cli_integration.py
    ├── test_config.py
    ├── test_csv_parser.py
    ├── test_dedup.py
    ├── test_gnucash_writer.py
    ├── test_gtk_app.py
    ├── test_journal.py
    ├── test_reports.py
    ├── test_rules_db.py
    ├── test_vat.py
    └── fixtures/
        └── sample_bank.csv
```

## License

MIT
