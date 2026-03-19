## Context

This is Phase 4 (CLI, Config, and Polish) — the final integration phase. All core modules already exist: csv_parser, dedup, categorizer, rules_db, gnucash_writer, gtk_app, and reports. The CLI stub in `bokforing/cli.py` and the `__main__.py` entry point were created during project scaffolding but contain only placeholder logic. The rules.db schema already defines `config` and `import_log` tables (see SPECIFICATION.md section 4.2).

## Goals / Non-Goals

**Goals:**
- Complete CLI UX with clear subcommands matching SPECIFICATION.md sections 5.1–5.5
- Configuration persistence in the rules.db `config` table (gnucash_book_path, company_name, org_nummer, company_address)
- First-time setup wizard (`bokforing init`) that creates the rules database and prompts for all config values
- The `import` subcommand orchestrates the full pipeline end-to-end
- Clear, actionable error messages for all failure modes
- Import log tracking (recording each import's stats in the `import_log` table)
- Defined exit codes for scripting (0=success, 1=parse error, 2=GnuCash error, 3=user cancelled)

**Non-Goals:**
- Shell completion (tab completion for subcommands/flags)
- Interactive mode beyond the init wizard (the GTK4 GUI handles interactive categorization)
- Daemon/watch mode for automatic CSV import
- Multi-language CLI output (Swedish only for now, matching the domain)

## Decisions

### 1. Use argparse from Python stdlib
**Rationale**: No extra dependency. The CLI has a small, fixed set of subcommands. argparse handles subparsers well and is familiar to Python developers.
**Alternative considered**: click — more ergonomic but adds a dependency for marginal benefit.

### 2. Store configuration in rules.db config table
**Rationale**: The rules.db schema already defines a `config` table (key-value TEXT pairs). Reusing it avoids a separate config file and keeps all tool state in one database. ConfigManager wraps simple SQL reads/writes.
**Alternative considered**: TOML/YAML config file in `~/.config/bokforing/` — adds file management complexity and a second state location.

### 3. Init wizard uses input() prompts
**Rationale**: Simple, no dependencies. The wizard runs once (or rarely). It prompts for GnuCash book path (with default path resolution), company name, org_nummer, and address. Validates the GnuCash path exists before saving.
**Alternative considered**: GTK4 dialog — overkill for a one-time setup; also would fail if GTK4 is not available.

### 4. Import subcommand orchestrates the full pipeline
**Rationale**: The import flow is linear: parse CSV → filter duplicates → categorize → launch GUI → write to GnuCash → log import. The CLI module calls each component in sequence and handles errors at each stage with appropriate exit codes.

### 5. Default GnuCash book path resolution
**Rationale**: GnuCash SQLite books are commonly stored in `~/.local/share/gnucash/` or the user's home directory. The init wizard prompts for the path; subsequent commands read it from config. The `--book` flag on `import` and `report` overrides the stored path.

## Risks / Trade-offs

- **[Risk] Config table doesn't exist yet in user's rules.db** → Mitigation: ConfigManager creates the table if missing (idempotent schema init)
- **[Risk] GnuCash book path becomes stale** → Mitigation: Validate path at command invocation time; clear error message if file not found
- **[Risk] GTK4 not available in headless environments** → Mitigation: `--no-gui` flag on import provides CLI-only fallback
- **[Trade-off] Single rules.db for both rules and config** → Simpler deployment but couples concerns; acceptable for a single-user tool
