## Context

The categorization engine (`bokforing.categorizer`) needs a persistent store for pattern-matching rules that map transaction text to BAS 2023 accounts. This database is deliberately separate from the GnuCash book so that rules survive GnuCash upgrades, can be backed up independently via JSON export, and do not interfere with the accounting data. The SPECIFICATION.md section 3.4 defines the interface and section 4.2 defines the schema.

## Goals / Non-Goals

**Goals:**
- CRUD operations on categorization rules (create, read, update, delete)
- Pattern-based lookup: exact match (highest priority), then contains match, with last_used as tiebreaker
- Track usage timestamps and counts for rule ranking
- JSON export/import for backup and portability
- File-level security (0600 permissions on the database file)

**Non-Goals:**
- Complex querying or full-text search beyond exact/contains matching
- ORM or abstraction layer (direct sqlite3 usage is sufficient)
- Multi-user or concurrent access (single-user desktop tool)
- Migration framework (schema is simple and stable)

## Decisions

### 1. SQLite via Python stdlib `sqlite3`
**Rationale**: Zero external dependencies. SQLite is perfectly suited for a single-user desktop application with ~50-100 rules. The stdlib `sqlite3` module provides everything needed.
**Alternative considered**: SQLAlchemy/ORM — unnecessary complexity for a three-table schema with simple queries.

### 2. Database file at `~/.local/share/bokforing/rules.db`
**Rationale**: Follows the XDG Base Directory Specification for application data on Linux. The parent directory is created automatically if it does not exist.
**Alternative considered**: Storing alongside the GnuCash book — rejected to maintain decoupling.

### 3. File permissions 0600 on database creation
**Rationale**: The database may contain business-sensitive information (transaction patterns, account mappings). Owner-only read/write prevents other users on the system from reading it. Set via `os.chmod()` after creation.

### 4. Schema with three tables: `rules`, `config`, `import_log`
**Rationale**: `rules` is the core table for categorization patterns. `config` provides key-value storage for application settings (GnuCash path, company info). `import_log` tracks CSV import history for auditing. All defined in SPECIFICATION.md section 4.2.

### 5. UNIQUE constraint on (pattern, match_type)
**Rationale**: Prevents duplicate rules for the same pattern and match type. `save_rule` uses INSERT OR REPLACE to implement upsert semantics — if a rule with the same pattern and match_type exists, it is updated rather than duplicated.

### 6. Pattern matching priority: exact > contains > most recently used
**Rationale**: Exact matches are most specific and should always win. Among contains matches, the most recently used rule is likely the most relevant. This matches the categorizer's expected behavior from SPECIFICATION.md section 3.3.

## Risks / Trade-offs

- **[Risk] Database file deleted or corrupted** -> Mitigation: JSON export provides a portable backup mechanism; import can restore from backup
- **[Risk] Parent directory does not exist** -> Mitigation: `__init__` creates `~/.local/share/bokforing/` with `os.makedirs(exist_ok=True)` before opening the database
- **[Trade-off] No schema migration system** -> Accepted: the schema is simple and unlikely to change frequently. If needed, version can be tracked in the `config` table and migrations applied in `__init__`
