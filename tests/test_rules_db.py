"""Tests for the rules database module (bookkeeping.rules_db).

Covers database initialisation, CRUD operations, pattern matching priority,
and JSON export/import round-trips.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bookkeeping.models import Rule, RulesDBError
from bookkeeping.rules_db import RulesDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rule(
    pattern: str = "Spotify",
    match_type: str = "exact",
    debit_account: int = 6540,
    credit_account: int = 1930,
    vat_rate: str = "0.25",
    vat_account: int | None = 2640,
    last_used: date = date(2026, 3, 1),
    use_count: int = 1,
) -> Rule:
    """Create a Rule with sensible defaults for testing."""
    return Rule(
        id=None,
        pattern=pattern,
        match_type=match_type,
        debit_account=debit_account,
        credit_account=credit_account,
        vat_rate=Decimal(vat_rate),
        vat_account=vat_account,
        last_used=last_used,
        use_count=use_count,
    )


@pytest.fixture
def db(tmp_path: Path) -> RulesDatabase:
    """Provide a fresh RulesDatabase in a temporary directory."""
    return RulesDatabase(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# 8.1 — Database initialisation
# ---------------------------------------------------------------------------

class TestDatabaseInitialisation:
    """Tests for __init__: table creation, permissions, directory creation."""

    def test_tables_created(self, db: RulesDatabase, tmp_path: Path) -> None:
        """All three tables exist after initialisation."""
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "config" in tables
        assert "import_log" in tables
        assert "rules" in tables

    def test_file_permissions(self, tmp_path: Path) -> None:
        """Database file is created with 0600 permissions."""
        db_path = tmp_path / "secure.db"
        RulesDatabase(db_path)

        file_mode = stat.S_IMODE(os.stat(db_path).st_mode)
        assert file_mode == 0o600

    def test_parent_directory_created(self, tmp_path: Path) -> None:
        """Parent directories are created if they do not exist."""
        nested_path = tmp_path / "deep" / "nested" / "dir" / "rules.db"
        RulesDatabase(nested_path)

        assert nested_path.exists()

    def test_existing_database_preserves_data(self, tmp_path: Path) -> None:
        """Opening an existing database does not destroy data."""
        db_path = tmp_path / "persistent.db"
        db1 = RulesDatabase(db_path)
        db1.save_rule(_make_rule(pattern="TestRule"))

        # Re-open the same database
        db2 = RulesDatabase(db_path)
        rules = db2.list_rules()
        assert len(rules) == 1
        assert rules[0].pattern == "TestRule"


# ---------------------------------------------------------------------------
# 8.2 — find_rule
# ---------------------------------------------------------------------------

class TestFindRule:
    """Tests for find_rule: priority, case-insensitivity, tiebreaker, None."""

    def test_exact_match_priority(self, db: RulesDatabase) -> None:
        """Exact match takes priority over contains match."""
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact"))
        db.save_rule(_make_rule(pattern="Spot", match_type="contains"))

        result = db.find_rule("Spotify")
        assert result is not None
        assert result.pattern == "Spotify"
        assert result.match_type == "exact"

    def test_contains_match_fallback(self, db: RulesDatabase) -> None:
        """Contains match is returned when no exact match exists."""
        db.save_rule(_make_rule(pattern="spotify", match_type="contains"))

        result = db.find_rule("Spotify AB 2026-01-15")
        assert result is not None
        assert result.pattern == "spotify"
        assert result.match_type == "contains"

    def test_contains_match_case_insensitive(self, db: RulesDatabase) -> None:
        """Contains matching is case-insensitive."""
        db.save_rule(_make_rule(pattern="SPOTIFY", match_type="contains"))

        result = db.find_rule("spotify ab monthly")
        assert result is not None
        assert result.pattern == "SPOTIFY"

    def test_most_recently_used_tiebreaker(self, db: RulesDatabase) -> None:
        """Among multiple contains matches, most recently used wins."""
        db.save_rule(
            _make_rule(
                pattern="bank",
                match_type="contains",
                debit_account=6570,
                last_used=date(2026, 3, 1),
            )
        )
        db.save_rule(
            _make_rule(
                pattern="bank",
                match_type="exact",
                debit_account=6540,
                last_used=date(2026, 3, 15),
            )
        )

        # Both could match "bank" exactly — but the exact match wins by priority
        result = db.find_rule("bank")
        assert result is not None
        assert result.match_type == "exact"

    def test_contains_tiebreaker_by_last_used(self, db: RulesDatabase) -> None:
        """Among contains matches, the most recently used rule is returned."""
        db.save_rule(
            _make_rule(
                pattern="soft",
                match_type="contains",
                debit_account=6540,
                last_used=date(2026, 3, 1),
            )
        )
        db.save_rule(
            _make_rule(
                pattern="ware",
                match_type="contains",
                debit_account=6212,
                last_used=date(2026, 3, 15),
            )
        )

        result = db.find_rule("Software subscription")
        assert result is not None
        # "ware" was used more recently
        assert result.pattern == "ware"
        assert result.last_used == date(2026, 3, 15)

    def test_no_match_returns_none(self, db: RulesDatabase) -> None:
        """None is returned when no rule matches."""
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact"))

        result = db.find_rule("Unknown Transaction XYZ")
        assert result is None

    def test_empty_database_returns_none(self, db: RulesDatabase) -> None:
        """None is returned from an empty database."""
        result = db.find_rule("anything")
        assert result is None


# ---------------------------------------------------------------------------
# 8.3 — save_rule
# ---------------------------------------------------------------------------

class TestSaveRule:
    """Tests for save_rule: insert and upsert."""

    def test_insert_new_rule(self, db: RulesDatabase) -> None:
        """A new rule is inserted into the database."""
        rule = _make_rule(pattern="Spotify", match_type="exact")
        db.save_rule(rule)

        rules = db.list_rules()
        assert len(rules) == 1
        assert rules[0].pattern == "Spotify"
        assert rules[0].match_type == "exact"
        assert rules[0].debit_account == 6540
        assert rules[0].id is not None

    def test_upsert_existing_rule(self, db: RulesDatabase) -> None:
        """Saving a rule with the same (pattern, match_type) updates it."""
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact", debit_account=6540))
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact", debit_account=6212))

        rules = db.list_rules()
        assert len(rules) == 1
        assert rules[0].debit_account == 6212

    def test_different_match_types_are_separate(self, db: RulesDatabase) -> None:
        """Same pattern with different match_type creates two separate rules."""
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact"))
        db.save_rule(_make_rule(pattern="Spotify", match_type="contains"))

        rules = db.list_rules()
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# 8.4 — update_last_used
# ---------------------------------------------------------------------------

class TestUpdateLastUsed:
    """Tests for update_last_used: timestamp and use_count."""

    def test_updates_timestamp_and_count(self, db: RulesDatabase) -> None:
        """last_used is set to today and use_count incremented by 1."""
        rule = _make_rule(last_used=date(2026, 1, 1), use_count=5)
        db.save_rule(rule)

        saved = db.list_rules()[0]
        db.update_last_used(saved.id)

        updated = db.list_rules()[0]
        assert updated.last_used == date.today()
        assert updated.use_count == 6

    def test_multiple_updates_increment_count(self, db: RulesDatabase) -> None:
        """Calling update_last_used multiple times increments use_count each time."""
        db.save_rule(_make_rule(use_count=1))
        saved = db.list_rules()[0]

        db.update_last_used(saved.id)
        db.update_last_used(saved.id)
        db.update_last_used(saved.id)

        updated = db.list_rules()[0]
        assert updated.use_count == 4


# ---------------------------------------------------------------------------
# 8.5 — list_rules
# ---------------------------------------------------------------------------

class TestListRules:
    """Tests for list_rules: ordering and empty database."""

    def test_correct_ordering(self, db: RulesDatabase) -> None:
        """Rules are returned ordered by last_used DESC."""
        db.save_rule(_make_rule(pattern="old", match_type="exact", last_used=date(2026, 1, 1)))
        db.save_rule(_make_rule(pattern="mid", match_type="exact", last_used=date(2026, 2, 1)))
        db.save_rule(_make_rule(pattern="new", match_type="exact", last_used=date(2026, 3, 1)))

        rules = db.list_rules()
        assert [r.pattern for r in rules] == ["new", "mid", "old"]

    def test_empty_database(self, db: RulesDatabase) -> None:
        """Empty database returns an empty list."""
        assert db.list_rules() == []


# ---------------------------------------------------------------------------
# 8.6 — delete_rule
# ---------------------------------------------------------------------------

class TestDeleteRule:
    """Tests for delete_rule: deletion and no-op on missing ID."""

    def test_successful_deletion(self, db: RulesDatabase) -> None:
        """A rule is removed and no longer findable."""
        db.save_rule(_make_rule(pattern="ToDelete", match_type="exact"))
        saved = db.list_rules()[0]

        db.delete_rule(saved.id)

        assert db.list_rules() == []
        assert db.find_rule("ToDelete") is None

    def test_delete_nonexistent_id(self, db: RulesDatabase) -> None:
        """Deleting a non-existent ID does not raise an error."""
        db.delete_rule(999)  # Should not raise


# ---------------------------------------------------------------------------
# 8.7 — export_rules and import_rules
# ---------------------------------------------------------------------------

class TestExportImport:
    """Tests for JSON export/import: round-trip and upsert on import."""

    def test_round_trip(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Exporting then importing produces the same data."""
        db.save_rule(_make_rule(pattern="Spotify", match_type="exact", debit_account=6540))
        db.save_rule(_make_rule(pattern="bank", match_type="contains", debit_account=6570))
        db.save_rule(
            _make_rule(
                pattern="Google",
                match_type="exact",
                debit_account=3040,
                vat_account=None,
                vat_rate="0.00",
            )
        )

        export_path = tmp_path / "rules_export.json"
        db.export_rules(export_path)

        # Verify the exported file is valid JSON
        with open(export_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert len(data) == 3

        # Import into a fresh database
        db2 = RulesDatabase(tmp_path / "import_test.db")
        db2.import_rules(export_path)

        imported = db2.list_rules()
        assert len(imported) == 3

        # Verify field values survive the round-trip
        spotify_rules = [r for r in imported if r.pattern == "Spotify"]
        assert len(spotify_rules) == 1
        assert spotify_rules[0].debit_account == 6540
        assert spotify_rules[0].vat_rate == Decimal("0.25")

    def test_upsert_on_import(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Importing updates existing rules rather than duplicating them."""
        db.save_rule(
            _make_rule(pattern="Spotify", match_type="exact", debit_account=6540)
        )

        # Create a JSON file with the same pattern but different account
        export_data = [
            {
                "pattern": "Spotify",
                "match_type": "exact",
                "debit_account": 6212,
                "credit_account": 1930,
                "vat_rate": "0.25",
                "vat_account": 2640,
                "last_used": "2026-03-15",
                "use_count": 3,
            }
        ]
        import_path = tmp_path / "import.json"
        with open(import_path, "w", encoding="utf-8") as fh:
            json.dump(export_data, fh)

        db.import_rules(import_path)

        rules = db.list_rules()
        assert len(rules) == 1
        assert rules[0].debit_account == 6212

    def test_import_does_not_write_to_import_log(
        self, db: RulesDatabase, tmp_path: Path
    ) -> None:
        """Rule import does not write to import_log (reserved for CSV imports)."""
        import sqlite3

        export_data = [
            {
                "pattern": "Test",
                "match_type": "exact",
                "debit_account": 6540,
                "credit_account": 1930,
                "vat_rate": "0.25",
                "vat_account": 2640,
                "last_used": "2026-03-01",
                "use_count": 1,
            }
        ]
        import_path = tmp_path / "log_test.json"
        with open(import_path, "w", encoding="utf-8") as fh:
            json.dump(export_data, fh)

        db.import_rules(import_path)

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute("SELECT COUNT(*) FROM import_log")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

    def test_export_empty_database(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Exporting an empty database produces an empty JSON array."""
        export_path = tmp_path / "empty.json"
        db.export_rules(export_path)

        with open(export_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data == []


# ---------------------------------------------------------------------------
# 8.8 — Context manager and close
# ---------------------------------------------------------------------------

class TestContextManager:
    """Tests for close(), __enter__, and __exit__."""

    def test_close_method(self, tmp_path: Path) -> None:
        """close() shuts the connection without error."""
        db = RulesDatabase(tmp_path / "close_test.db")
        db.save_rule(_make_rule(pattern="BeforeClose"))
        db.close()

        # Re-open to verify data was persisted before close
        db2 = RulesDatabase(tmp_path / "close_test.db")
        assert len(db2.list_rules()) == 1
        db2.close()

    def test_context_manager(self, tmp_path: Path) -> None:
        """RulesDatabase can be used as a context manager."""
        db_path = tmp_path / "ctx.db"
        with RulesDatabase(db_path) as db:
            db.save_rule(_make_rule(pattern="InContext"))

        # Re-open to verify data persisted and connection was closed
        with RulesDatabase(db_path) as db2:
            rules = db2.list_rules()
            assert len(rules) == 1
            assert rules[0].pattern == "InContext"


# ---------------------------------------------------------------------------
# 8.9 — LIKE wildcard escaping in find_rule
# ---------------------------------------------------------------------------

class TestFindRuleWildcardEscaping:
    """Tests that SQL LIKE wildcards in rule patterns do not cause false matches."""

    def test_percent_in_pattern_does_not_wildcard(self, db: RulesDatabase) -> None:
        """A pattern containing '%' matches literally, not as a LIKE wildcard."""
        db.save_rule(_make_rule(pattern="100%", match_type="contains"))

        # "100%" should match text containing the literal string "100%"
        assert db.find_rule("Discount 100% off") is not None
        # "1000 SEK" should NOT match — '%' is not a wildcard
        assert db.find_rule("1000 SEK") is None

    def test_underscore_in_pattern_does_not_wildcard(self, db: RulesDatabase) -> None:
        """A pattern containing '_' matches literally, not as a LIKE wildcard."""
        db.save_rule(_make_rule(pattern="item_name", match_type="contains"))

        assert db.find_rule("buy item_name here") is not None
        # "item3name" should NOT match — '_' is not a single-char wildcard
        assert db.find_rule("buy item3name here") is None


# ---------------------------------------------------------------------------
# 8.10 — Error handling paths
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests for RulesDBError on invalid inputs."""

    def test_import_nonexistent_file(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Importing a non-existent file raises RulesDBError."""
        with pytest.raises(RulesDBError, match="Failed to read rules"):
            db.import_rules(tmp_path / "does_not_exist.json")

    def test_import_invalid_json(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Importing a file with invalid JSON raises RulesDBError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")

        with pytest.raises(RulesDBError, match="Failed to read rules"):
            db.import_rules(bad_file)

    def test_import_non_array_json(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Importing a JSON object (not array) raises RulesDBError."""
        obj_file = tmp_path / "object.json"
        obj_file.write_text('{"key": "value"}', encoding="utf-8")

        with pytest.raises(RulesDBError, match="Expected a JSON array"):
            db.import_rules(obj_file)

    def test_export_to_unwritable_path(self, db: RulesDatabase, tmp_path: Path) -> None:
        """Exporting to a path where the parent doesn't exist raises RulesDBError."""
        bad_path = tmp_path / "nonexistent_dir" / "subdir" / "rules.json"

        with pytest.raises(RulesDBError, match="Failed to export rules"):
            db.export_rules(bad_path)
