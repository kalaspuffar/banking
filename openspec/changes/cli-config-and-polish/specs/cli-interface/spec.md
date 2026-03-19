## ADDED Requirements

### Requirement: Import subcommand
The system SHALL provide a `bookkeeping import <csv_file>` subcommand that orchestrates the full import pipeline: parse CSV, filter duplicates, categorize transactions, launch the GTK4 verification GUI, and write confirmed transactions to GnuCash.

#### Scenario: Successful import with GUI
- **WHEN** `bookkeeping import transactions.csv` is run with a valid CSV and configured GnuCash book
- **THEN** the system parses the CSV, filters duplicates, applies categorization rules, launches the GTK4 GUI for verification, writes confirmed transactions to GnuCash, logs the import, and exits with code 0

#### Scenario: Import with --dry-run
- **WHEN** `bookkeeping import transactions.csv --dry-run` is run
- **THEN** the system parses, deduplicates, and categorizes but does not write to GnuCash or launch the GUI, and prints a summary of what would be imported

#### Scenario: Import with --no-gui
- **WHEN** `bookkeeping import transactions.csv --no-gui` is run
- **THEN** the system uses CLI-only mode showing suggestions and requiring text-based confirmation instead of the GTK4 GUI

#### Scenario: Import with --book override
- **WHEN** `bookkeeping import transactions.csv --book /path/to/other.gnucash` is run
- **THEN** the specified GnuCash book is used instead of the configured default

### Requirement: Report subcommand
The system SHALL provide a `bookkeeping report <type> <year>` subcommand that generates PDF reports from GnuCash data.

#### Scenario: Generate momsdeklaration report
- **WHEN** `bookkeeping report moms 2025` is run
- **THEN** a PDF file `momsdeklaration_2025.pdf` is generated in the output directory

#### Scenario: Generate all reports
- **WHEN** `bookkeeping report all 2025` is run
- **THEN** PDF files for momsdeklaration, NE-bilaga, grundbok, and huvudbok are all generated for fiscal year 2025

#### Scenario: Custom output directory
- **WHEN** `bookkeeping report moms 2025 --output-dir /tmp/reports` is run
- **THEN** the PDF is written to `/tmp/reports/momsdeklaration_2025.pdf`

#### Scenario: Default output directory
- **WHEN** `bookkeeping report moms 2025` is run without `--output-dir`
- **THEN** the PDF is written to `./rapporter/momsdeklaration_2025.pdf`

### Requirement: Rules management subcommands
The system SHALL provide `bookkeeping rules` subcommands for managing categorization rules.

#### Scenario: List all rules
- **WHEN** `bookkeeping rules list` is run
- **THEN** all stored categorization rules are displayed in a tabular format showing id, pattern, match_type, debit_account, credit_account, vat_rate, and use_count

#### Scenario: Delete a rule
- **WHEN** `bookkeeping rules delete 5` is run
- **THEN** the rule with id 5 is removed from the rules database

#### Scenario: Export rules to JSON
- **WHEN** `bookkeeping rules export backup.json` is run
- **THEN** all rules are exported to `backup.json` in JSON format

#### Scenario: Import rules from JSON
- **WHEN** `bookkeeping rules import backup.json` is run
- **THEN** rules from `backup.json` are imported into the rules database

### Requirement: Config subcommands
The system SHALL provide `bookkeeping config` subcommands for viewing and setting configuration.

#### Scenario: Show current configuration
- **WHEN** `bookkeeping config show` is run
- **THEN** all current configuration key-value pairs are displayed

#### Scenario: Set a config value
- **WHEN** `bookkeeping config set gnucash_book_path /home/user/books/main.gnucash` is run
- **THEN** the gnucash_book_path config key is updated in the rules.db config table

### Requirement: Init wizard
The system SHALL provide a `bookkeeping init` subcommand that performs first-time setup.

#### Scenario: First-time init
- **WHEN** `bookkeeping init` is run for the first time
- **THEN** it creates the rules database at `~/.local/share/bookkeeping/rules.db`, prompts for GnuCash book path, company name, organisationsnummer, and company address, validates the GnuCash book path exists, and saves all values to the config table

#### Scenario: Re-running init
- **WHEN** `bookkeeping init` is run when a rules database already exists
- **THEN** it shows current values as defaults and allows the user to update them

### Requirement: Exit codes
The system SHALL use defined exit codes: 0 for success, 1 for CSV parse errors, 2 for GnuCash errors (file not found, locked, write failure), and 3 for user cancellation.

#### Scenario: CSV parse error exit code
- **WHEN** an import fails due to a malformed CSV
- **THEN** the process exits with code 1 and prints a descriptive error message

#### Scenario: GnuCash error exit code
- **WHEN** an import fails because the GnuCash file is locked or missing
- **THEN** the process exits with code 2 and prints a descriptive error message

#### Scenario: User cancellation exit code
- **WHEN** the user cancels the import in the GTK4 GUI
- **THEN** the process exits with code 3

### Requirement: Import log tracking
The system SHALL record each import operation in the `import_log` table of rules.db, storing the CSV filename, total transaction count, new transaction count, duplicate count, and error count.

#### Scenario: Successful import is logged
- **WHEN** an import of 10 transactions completes with 8 new, 2 duplicates, and 0 errors
- **THEN** a row is inserted into import_log with transactions_total=10, transactions_new=8, transactions_dup=2, transactions_error=0
