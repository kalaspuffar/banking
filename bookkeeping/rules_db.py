"""SQLite-backed categorization rules database.

Persists pattern-matching rules that map bank transaction text to BAS 2023
accounts. The database is stored separately from GnuCash to allow independent
backup, export, and upgrade. See SPECIFICATION.md section 4.2 for the schema.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from bookkeeping.models import MatchType, Rule, RulesDBError

# ---------------------------------------------------------------------------
# SQL schema constants (matching SPECIFICATION.md section 4.2)
# ---------------------------------------------------------------------------

_CREATE_RULES_TABLE = """\
CREATE TABLE IF NOT EXISTS rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern         TEXT NOT NULL,
    match_type      TEXT NOT NULL DEFAULT 'contains',
    debit_account   INTEGER NOT NULL,
    credit_account  INTEGER NOT NULL,
    vat_rate        TEXT NOT NULL DEFAULT '0.00',
    vat_account     INTEGER,
    last_used       TEXT NOT NULL,
    use_count       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(pattern, match_type)
);
"""

_CREATE_CONFIG_TABLE = """\
CREATE TABLE IF NOT EXISTS config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

_CREATE_IMPORT_LOG_TABLE = """\
CREATE TABLE IF NOT EXISTS import_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    import_date         TEXT NOT NULL DEFAULT (datetime('now')),
    csv_filename        TEXT NOT NULL,
    transactions_total  INTEGER NOT NULL,
    transactions_new    INTEGER NOT NULL,
    transactions_dup    INTEGER NOT NULL,
    transactions_error  INTEGER NOT NULL
);
"""

_CREATE_INDEX_PATTERN = (
    "CREATE INDEX IF NOT EXISTS idx_rules_pattern ON rules(pattern);"
)

_CREATE_INDEX_LAST_USED = (
    "CREATE INDEX IF NOT EXISTS idx_rules_last_used ON rules(last_used DESC);"
)


def _row_to_rule(row: sqlite3.Row) -> Rule:
    """Convert a database row to a Rule dataclass."""
    return Rule(
        id=row["id"],
        pattern=row["pattern"],
        match_type=row["match_type"],
        debit_account=row["debit_account"],
        credit_account=row["credit_account"],
        vat_rate=Decimal(row["vat_rate"]),
        vat_account=row["vat_account"],
        last_used=date.fromisoformat(row["last_used"]),
        use_count=row["use_count"],
    )


def _rule_to_dict(rule: Rule) -> dict:
    """Convert a Rule dataclass to a JSON-serialisable dictionary.

    Note: match_type is a Literal["exact", "contains"] type alias, not an enum.
    It serialises directly as a plain string.
    """
    return {
        "pattern": rule.pattern,
        "match_type": rule.match_type,
        "debit_account": rule.debit_account,
        "credit_account": rule.credit_account,
        "vat_rate": str(rule.vat_rate),
        "vat_account": rule.vat_account,
        "last_used": rule.last_used.isoformat(),
        "use_count": rule.use_count,
    }


def _dict_to_rule(data: dict) -> Rule:
    """Convert a JSON-deserialised dictionary to a Rule dataclass."""
    return Rule(
        id=None,
        pattern=data["pattern"],
        match_type=data["match_type"],
        debit_account=data["debit_account"],
        credit_account=data["credit_account"],
        vat_rate=Decimal(data["vat_rate"]),
        vat_account=data.get("vat_account"),
        last_used=date.fromisoformat(data["last_used"]),
        use_count=data.get("use_count", 1),
    )


class RulesDatabase:
    """SQLite-backed storage for categorization rules.

    Creates the database file and schema on first use. The database file
    is set to 0600 permissions (owner read/write only) for security.

    Args:
        db_path: Path to the SQLite database file. Parent directories
            are created automatically if they do not exist.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(_CREATE_RULES_TABLE)
            self._conn.execute(_CREATE_CONFIG_TABLE)
            self._conn.execute(_CREATE_IMPORT_LOG_TABLE)
            self._conn.execute(_CREATE_INDEX_PATTERN)
            self._conn.execute(_CREATE_INDEX_LAST_USED)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to initialise database at {db_path}: {exc}") from exc

        self._db_path.chmod(0o600)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> RulesDatabase:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Find rule with priority logic
    # ------------------------------------------------------------------

    def find_rule(self, transaction_text: str) -> Rule | None:
        """Look up a matching rule for the given transaction text.

        Search priority:
        1. Exact match on pattern (match_type='exact'), most recently used first.
        2. Contains match (case-insensitive), most recently used first.

        Args:
            transaction_text: The bank transaction description to match against.

        Returns:
            The best matching Rule, or None if no rule matches.
        """
        try:
            # Priority 1: exact match
            cursor = self._conn.execute(
                "SELECT * FROM rules "
                "WHERE match_type = 'exact' AND pattern = ? "
                "ORDER BY last_used DESC LIMIT 1",
                (transaction_text,),
            )
            row = cursor.fetchone()
            if row is not None:
                return _row_to_rule(row)

            # Priority 2: contains match (case-insensitive via LOWER).
            # SQLite LIKE is case-insensitive for ASCII but not for Unicode
            # characters (å, ä, ö), so we use LOWER() on both sides.
            # Patterns are escaped to prevent SQL LIKE wildcards (% _) in
            # rule patterns from matching unintended text.
            cursor = self._conn.execute(
                "SELECT * FROM rules "
                "WHERE match_type = 'contains' "
                "AND LOWER(?) LIKE '%' || REPLACE(REPLACE(REPLACE("
                "LOWER(pattern), '\\', '\\\\'), '%', '\\%'), '_', '\\_') || '%' "
                "ESCAPE '\\' "
                "ORDER BY last_used DESC LIMIT 1",
                (transaction_text,),
            )
            row = cursor.fetchone()
            if row is not None:
                return _row_to_rule(row)

        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to find rule for {transaction_text!r}: {exc}") from exc

        return None

    # ------------------------------------------------------------------
    # Save rule with upsert semantics
    # ------------------------------------------------------------------

    def save_rule(self, rule: Rule) -> None:
        """Insert a new rule or update an existing one.

        Uses INSERT OR REPLACE to handle the UNIQUE(pattern, match_type)
        constraint. On insert, created_at is set automatically by the
        database default. On every save, updated_at is set to now.

        Args:
            rule: The rule to save. The id field is ignored for upsert
                matching — the UNIQUE constraint on (pattern, match_type)
                determines whether this is an insert or an update.
        """
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        try:
            self._conn.execute(
                "INSERT INTO rules "
                "(pattern, match_type, debit_account, credit_account, "
                "vat_rate, vat_account, last_used, use_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(pattern, match_type) DO UPDATE SET "
                "debit_account = excluded.debit_account, "
                "credit_account = excluded.credit_account, "
                "vat_rate = excluded.vat_rate, "
                "vat_account = excluded.vat_account, "
                "last_used = excluded.last_used, "
                "use_count = excluded.use_count, "
                "updated_at = excluded.updated_at",
                (
                    rule.pattern,
                    rule.match_type,
                    rule.debit_account,
                    rule.credit_account,
                    str(rule.vat_rate),
                    rule.vat_account,
                    rule.last_used.isoformat(),
                    rule.use_count,
                    now,
                    now,
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to save rule {rule.pattern!r}: {exc}") from exc

    # ------------------------------------------------------------------
    # Update last used
    # ------------------------------------------------------------------

    def update_last_used(self, rule_id: int) -> None:
        """Update the last_used date and increment use_count for a rule.

        Args:
            rule_id: The database ID of the rule to update.
        """
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        today = date.today().isoformat()
        try:
            self._conn.execute(
                "UPDATE rules SET last_used = ?, use_count = use_count + 1, "
                "updated_at = ? WHERE id = ?",
                (today, now, rule_id),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to update last_used for rule {rule_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # List and delete
    # ------------------------------------------------------------------

    def list_rules(self) -> list[Rule]:
        """Return all rules ordered by last_used DESC.

        Returns:
            List of all rules, most recently used first. Empty list if
            no rules exist.
        """
        try:
            cursor = self._conn.execute(
                "SELECT * FROM rules ORDER BY last_used DESC"
            )
            return [_row_to_rule(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to list rules: {exc}") from exc

    def delete_rule(self, rule_id: int) -> None:
        """Delete a rule by its database ID.

        No error is raised if the rule does not exist.

        Args:
            rule_id: The database ID of the rule to delete.
        """
        try:
            self._conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to delete rule {rule_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Export / import JSON
    # ------------------------------------------------------------------

    def export_rules(self, filepath: Path) -> None:
        """Export all rules to a JSON file.

        Args:
            filepath: Destination file path. Parent directories must exist.
        """
        rules = self.list_rules()
        data = [_rule_to_dict(rule) for rule in rules]
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            raise RulesDBError(f"Failed to export rules to {filepath}: {exc}") from exc

    def import_rules(self, filepath: Path) -> None:
        """Import rules from a JSON file using upsert semantics.

        Each rule in the JSON array is saved via save_rule, so existing
        rules with the same (pattern, match_type) are updated rather
        than duplicated.

        Note: the import_log table is reserved for CSV import operations
        (see SPECIFICATION.md Section 4.2), so rule imports are not logged there.

        Args:
            filepath: Path to a JSON file containing an array of rule objects.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise RulesDBError(f"Failed to read rules from {filepath}: {exc}") from exc

        if not isinstance(data, list):
            raise RulesDBError(
                f"Expected a JSON array in {filepath}, got {type(data).__name__}"
            )

        for entry in data:
            rule = _dict_to_rule(entry)
            self.save_rule(rule)
