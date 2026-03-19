## Why

The tool needs a complete CLI interface tying all components together, plus configuration management and a first-time setup wizard. All core modules (csv_parser, dedup, categorizer, rules_db, gnucash_writer, gtk_app, reports) exist, but there is no unified entry point that orchestrates them. This is the final integration phase (Phase 4 in the implementation plan) that makes the tool usable end-to-end via the `bokforing` command.

## What Changes

- Implement full argparse CLI in `bokforing/cli.py` with subcommands: `import`, `report`, `rules`, `config`, `init`
- Implement `bokforing/config.py` with `ConfigManager` class for reading/writing configuration from the `config` table in `rules.db`
- Implement `bokforing init` first-time setup wizard that creates the rules database, prompts for GnuCash book path, company name, organisationsnummer, and company address
- The `import` subcommand orchestrates the full pipeline: CSV parse → duplicate detection → categorization → GTK4 GUI → GnuCash write
- Defined exit codes: 0=success, 1=parse error, 2=GnuCash error, 3=user cancelled
- Import log tracking via the `import_log` table in rules.db
- Replace the existing CLI stub in `bokforing/cli.py` with the full implementation
- Write integration tests for CLI subcommands

## Capabilities

### New Capabilities
- `cli-interface`: Full argparse CLI with import, report, rules, config, and init subcommands
- `configuration`: ConfigManager for persisting and retrieving settings from rules.db config table

### Modified Capabilities
<!-- Replaces the CLI stub from the project scaffolding phase -->

## Impact

- **Code**: Replaces `bokforing/cli.py` stub, adds new `bokforing/config.py`, adds integration tests
- **Dependencies**: Uses only Python stdlib (argparse, pathlib) plus existing project modules
- **Data**: Reads/writes the `config` table and `import_log` table in rules.db
- **Systems**: Integrates all existing modules into a cohesive user-facing tool
