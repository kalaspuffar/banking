## ADDED Requirements

### Requirement: Database initialization
The system SHALL create the SQLite database and all required tables (`rules`, `config`, `import_log`) when `RulesDatabase.__init__` is called and the tables do not yet exist.

#### Scenario: First-time initialization creates tables
- **WHEN** `RulesDatabase(db_path)` is called with a path where no database exists
- **THEN** the database file is created with tables `rules`, `config`, and `import_log` matching the schema in SPECIFICATION.md section 4.2

#### Scenario: Existing database is opened without modification
- **WHEN** `RulesDatabase(db_path)` is called with a path to an existing valid database
- **THEN** the database is opened and existing data is preserved

#### Scenario: Parent directory is created if missing
- **WHEN** `RulesDatabase(db_path)` is called and the parent directory does not exist
- **THEN** the parent directory is created with `os.makedirs(exist_ok=True)` before opening the database

### Requirement: File permissions
The system SHALL set file permissions to 0600 (owner read/write only) on the database file upon creation.

#### Scenario: New database has restricted permissions
- **WHEN** a new database file is created by `RulesDatabase.__init__`
- **THEN** the file permissions are 0600 (readable and writable only by the owner)

### Requirement: Find rule by transaction text
The system SHALL provide `find_rule(transaction_text: str) -> Rule | None` that searches for a matching rule using exact match first, then contains match, returning the most recently used match.

#### Scenario: Exact match takes priority
- **GIVEN** a rule with pattern "Spotify" and match_type "exact", and a rule with pattern "Spot" and match_type "contains"
- **WHEN** `find_rule("Spotify")` is called
- **THEN** the exact-match rule is returned

#### Scenario: Contains match when no exact match exists
- **GIVEN** a rule with pattern "spotify" and match_type "contains" (no exact match rule)
- **WHEN** `find_rule("Spotify AB 2026-01-15")` is called
- **THEN** the contains-match rule is returned (case-insensitive matching)

#### Scenario: Most recently used rule wins among multiple contains matches
- **GIVEN** two contains rules matching the same text, one with last_used "2026-03-01" and another with last_used "2026-03-15"
- **WHEN** `find_rule` is called with text matching both rules
- **THEN** the rule with last_used "2026-03-15" is returned

#### Scenario: No matching rule
- **WHEN** `find_rule("Unknown Transaction XYZ")` is called and no rule matches
- **THEN** `None` is returned

### Requirement: Save rule with upsert semantics
The system SHALL provide `save_rule(rule: Rule) -> None` that inserts a new rule or updates an existing one based on the UNIQUE constraint on (pattern, match_type).

#### Scenario: Insert new rule
- **WHEN** `save_rule` is called with a rule whose (pattern, match_type) combination does not exist
- **THEN** a new row is inserted into the `rules` table

#### Scenario: Update existing rule (upsert)
- **GIVEN** a rule with pattern "Spotify" and match_type "exact" already exists
- **WHEN** `save_rule` is called with the same pattern and match_type but different account mappings
- **THEN** the existing rule is updated with the new account mappings

### Requirement: Update last used timestamp
The system SHALL provide `update_last_used(rule_id: int) -> None` that updates the `last_used` date to today and increments `use_count` by 1.

#### Scenario: Successful update
- **GIVEN** a rule with id=1, last_used="2026-01-01", use_count=5
- **WHEN** `update_last_used(1)` is called
- **THEN** the rule has last_used set to today's date and use_count=6

### Requirement: List rules ordered by last used
The system SHALL provide `list_rules() -> list[Rule]` that returns all rules ordered by `last_used` DESC.

#### Scenario: Rules returned in order
- **GIVEN** three rules with last_used dates "2026-01-01", "2026-03-01", "2026-02-01"
- **WHEN** `list_rules()` is called
- **THEN** the rules are returned in order: "2026-03-01", "2026-02-01", "2026-01-01"

#### Scenario: Empty database returns empty list
- **WHEN** `list_rules()` is called on a database with no rules
- **THEN** an empty list is returned

### Requirement: Delete rule by ID
The system SHALL provide `delete_rule(rule_id: int) -> None` that removes a rule from the database by its ID.

#### Scenario: Successful deletion
- **GIVEN** a rule with id=1 exists
- **WHEN** `delete_rule(1)` is called
- **THEN** the rule is removed and `find_rule` no longer returns it

#### Scenario: Delete non-existent rule is a no-op
- **WHEN** `delete_rule(999)` is called and no rule with that ID exists
- **THEN** no error is raised

### Requirement: Export rules to JSON
The system SHALL provide `export_rules(filepath: Path) -> None` that writes all rules to a JSON file.

#### Scenario: Export produces valid JSON
- **GIVEN** a database with 3 rules
- **WHEN** `export_rules(Path("/tmp/rules.json"))` is called
- **THEN** the file contains a valid JSON array with 3 rule objects, each containing all rule fields

### Requirement: Import rules from JSON
The system SHALL provide `import_rules(filepath: Path) -> None` that reads rules from a JSON file and inserts them into the database using upsert semantics.

#### Scenario: Import new rules
- **GIVEN** an empty database and a JSON file with 3 rules
- **WHEN** `import_rules(Path("/tmp/rules.json"))` is called
- **THEN** all 3 rules are inserted into the database

#### Scenario: Import with existing rules uses upsert
- **GIVEN** a database with a rule for pattern "Spotify" match_type "exact"
- **AND** a JSON file containing a rule with the same pattern and match_type but different accounts
- **WHEN** `import_rules` is called
- **THEN** the existing rule is updated (not duplicated)

#### Scenario: Import logs the operation
- **WHEN** `import_rules` is called successfully
- **THEN** an entry is written to the `import_log` table (or the operation is otherwise auditable)
