## Why

The categorization engine needs persistent storage for its pattern-matching rules. Without a dedicated rules database, the system cannot learn from previous categorizations or suggest accounts for recurring transactions. Rules must survive between sessions and be independent of the GnuCash book to allow backup, export, and upgrade without affecting accounting data.

## What Changes

- Implement `bokforing/rules_db.py` with a `RulesDatabase` class providing:
  - `__init__(self, db_path: Path)` — open/create the SQLite database, create tables if not exist
  - `find_rule(self, transaction_text: str) -> Rule | None` — look up a matching rule (exact match first, then contains)
  - `save_rule(self, rule: Rule) -> None` — insert or update a rule with UNIQUE constraint on (pattern, match_type)
  - `update_last_used(self, rule_id: int) -> None` — touch the last_used timestamp and increment use_count
  - `list_rules(self) -> list[Rule]` — return all rules ordered by last_used DESC
  - `delete_rule(self, rule_id: int) -> None` — remove a rule by ID
  - `export_rules(self, filepath: Path) -> None` — export all rules to a JSON file
  - `import_rules(self, filepath: Path) -> None` — import rules from a JSON file, logging the operation
- SQLite database stored at `~/.local/share/bokforing/rules.db`
- Database schema includes three tables: `rules`, `config`, `import_log`
- Create comprehensive unit tests in `tests/test_rules_db.py`

## Capabilities

### New Capabilities
- `rules-storage`: SQLite-backed CRUD for categorization rules with pattern lookup, JSON export/import, and file-level security

### Modified Capabilities

## Impact

- **Code**: New module `bokforing/rules_db.py` and test file `tests/test_rules_db.py`
- **Dependencies**: Uses only Python stdlib (`sqlite3`, `json`, `pathlib`, `os`, `datetime`)
- **Data**: Creates and manages `~/.local/share/bokforing/rules.db` with `rules`, `config`, and `import_log` tables
- **Security**: Database file created with 0600 permissions (owner read/write only)
