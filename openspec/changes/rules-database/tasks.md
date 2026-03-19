## 1. Module Setup and Schema Constants

- [ ] 1.1 Create `bokforing/rules_db.py` with SQL schema constants for `rules`, `config`, and `import_log` tables matching SPECIFICATION.md section 4.2
- [ ] 1.2 Define `CREATE TABLE` and `CREATE INDEX` statements as module-level string constants

## 2. Database Initialization

- [ ] 2.1 Implement `RulesDatabase.__init__(self, db_path: Path)` that creates parent directories with `os.makedirs(exist_ok=True)`
- [ ] 2.2 Open SQLite connection with `sqlite3.connect()` and execute `CREATE TABLE IF NOT EXISTS` for all three tables and both indexes
- [ ] 2.3 Set file permissions to 0600 via `os.chmod()` after database creation

## 3. Find Rule with Priority Logic

- [ ] 3.1 Implement `find_rule(self, transaction_text: str) -> Rule | None`
- [ ] 3.2 First query: exact match on pattern where match_type='exact', ordered by last_used DESC, LIMIT 1
- [ ] 3.3 Second query (if no exact match): contains match where transaction_text LIKE '%' || pattern || '%' (case-insensitive) and match_type='contains', ordered by last_used DESC, LIMIT 1
- [ ] 3.4 Convert the row to a `Rule` dataclass and return, or return None if no match

## 4. Save Rule with Upsert

- [ ] 4.1 Implement `save_rule(self, rule: Rule) -> None` using `INSERT OR REPLACE INTO rules` to handle the UNIQUE(pattern, match_type) constraint
- [ ] 4.2 Set `updated_at` to current datetime on every save; set `created_at` only on insert

## 5. Update Last Used

- [ ] 5.1 Implement `update_last_used(self, rule_id: int) -> None` that sets `last_used` to today's ISO date, increments `use_count` by 1, and updates `updated_at`

## 6. List and Delete Rules

- [ ] 6.1 Implement `list_rules(self) -> list[Rule]` returning all rules ordered by `last_used DESC`
- [ ] 6.2 Implement `delete_rule(self, rule_id: int) -> None` that deletes by ID (no error if not found)

## 7. Export and Import JSON

- [ ] 7.1 Implement `export_rules(self, filepath: Path) -> None` that queries all rules and writes them as a JSON array to the given file path
- [ ] 7.2 Implement `import_rules(self, filepath: Path) -> None` that reads a JSON array of rules and inserts each using upsert semantics (reuse `save_rule`)

## 8. Tests

- [ ] 8.1 Create `tests/test_rules_db.py` with tests for: database initialization (tables created), file permissions (0600), parent directory creation
- [ ] 8.2 Add tests for `find_rule`: exact match priority, contains match fallback, case-insensitive contains, most-recently-used tiebreaker, no match returns None
- [ ] 8.3 Add tests for `save_rule`: insert new rule, upsert existing rule
- [ ] 8.4 Add tests for `update_last_used`: timestamp and use_count updated
- [ ] 8.5 Add tests for `list_rules`: correct ordering, empty database
- [ ] 8.6 Add tests for `delete_rule`: successful deletion, delete non-existent ID
- [ ] 8.7 Add tests for `export_rules` and `import_rules`: round-trip (export then import produces same data), upsert on import
