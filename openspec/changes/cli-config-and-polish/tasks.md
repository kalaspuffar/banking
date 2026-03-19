## 1. Configuration Management

- [ ] 1.1 Implement `bokforing/config.py` with `ConfigManager` class: `__init__(db_path)`, `get(key, default=None)`, `set(key, value)`, idempotent config table creation
- [ ] 1.2 Implement `find_default_book_path()` method that searches `~/.local/share/gnucash/` for `.gnucash` files
- [ ] 1.3 Implement `get_company_info(fiscal_year)` method that constructs a `CompanyInfo` dataclass from stored config values
- [ ] 1.4 Write unit tests in `tests/test_config.py` for ConfigManager: get/set, missing keys, defaults, table creation idempotency

## 2. Init Wizard

- [ ] 2.1 Implement the `init` subcommand handler that creates `~/.local/share/bokforing/` directory and `rules.db` database
- [ ] 2.2 Implement interactive prompts for GnuCash book path (with default from `find_default_book_path()`), company name, org_nummer, and company address
- [ ] 2.3 Validate that the provided GnuCash book path exists and is a valid file before saving
- [ ] 2.4 Support re-running init: show current values as defaults and allow updates

## 3. CLI Argument Parsing

- [ ] 3.1 Implement full argparse structure in `bokforing/cli.py` with subparsers for: `import`, `report`, `rules`, `config`, `init`
- [ ] 3.2 Implement `import` subparser with positional `csv_file` argument and optional `--book`, `--dry-run`, `--no-gui` flags
- [ ] 3.3 Implement `report` subparser with positional `type` (choices: moms, ne, grundbok, huvudbok, all) and `year` arguments, plus optional `--book` and `--output-dir` flags
- [ ] 3.4 Implement `rules` subparser with sub-subcommands: `list`, `delete <id>`, `export <file>`, `import <file>`
- [ ] 3.5 Implement `config` subparser with sub-subcommands: `show`, `set <key> <value>`

## 4. Import Orchestration

- [ ] 4.1 Implement the `import` command handler that orchestrates: parse_bank_csv → filter_duplicates → suggest_categorization → launch gtk_app → write_transactions
- [ ] 4.2 Implement `--dry-run` mode: parse, dedup, categorize, print summary without writing or launching GUI
- [ ] 4.3 Implement `--no-gui` mode: CLI-only display of suggestions with text-based confirmation
- [ ] 4.4 Implement GnuCash book path resolution: use `--book` flag if provided, otherwise read from config, error if neither available

## 5. Report Subcommand

- [ ] 5.1 Implement the `report` command handler that calls `generate_report()` with the correct arguments
- [ ] 5.2 Implement `all` report type that generates moms, ne, grundbok, and huvudbok in sequence
- [ ] 5.3 Implement default output directory (`./rapporter/`), creating it if it does not exist

## 6. Rules Management Subcommands

- [ ] 6.1 Implement `rules list` handler that displays all rules in a formatted table
- [ ] 6.2 Implement `rules delete <id>` handler with confirmation
- [ ] 6.3 Implement `rules export <file>` handler calling `rules_db.export_rules()`
- [ ] 6.4 Implement `rules import <file>` handler calling `rules_db.import_rules()`

## 7. Error Handling and Exit Codes

- [ ] 7.1 Implement error handling in the main entry point: catch CSVParseError → exit 1, GnuCash errors → exit 2, user cancellation → exit 3
- [ ] 7.2 Ensure all error paths print clear, actionable error messages to stderr

## 8. Import Log Tracking

- [ ] 8.1 Implement import log recording: after each import, insert a row into the `import_log` table with csv_filename, transactions_total, transactions_new, transactions_dup, transactions_error
- [ ] 8.2 Ensure import_log table is created if missing (idempotent schema init, same pattern as config table)

## 9. Integration Tests

- [ ] 9.1 Write integration tests in `tests/test_cli_integration.py` for: CLI argument parsing, init wizard (mocked input), import dry-run mode, config show/set, rules list
- [ ] 9.2 Write tests for exit code behavior: parse error returns 1, GnuCash error returns 2
