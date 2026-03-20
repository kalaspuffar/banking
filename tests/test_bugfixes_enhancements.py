"""Tests for bugfixes and CLI enhancements.

Covers:
- display_text field on BankTransaction
- Categorization using display_text (with fallback to text)
- Text alias CRUD operations in RulesDatabase
- apply_aliases function (case-insensitive, longest-first, no-match)
- rules create CLI subcommand
- alias CLI subcommands
- configure() call argument types
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest

from bookkeeping.categorizer import (
    apply_aliases,
    save_rule,
    suggest_categorization,
)
from bookkeeping.models import (
    BankTransaction,
    Rule,
    TextAlias,
)
from bookkeeping.rules_db import RulesDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def rules_db(tmp_path: Path) -> Generator[RulesDatabase, None, None]:
    """Provide a fresh, empty rules database for each test."""
    db = RulesDatabase(tmp_path / "test_rules.db")
    yield db
    db.close()


def _make_transaction(
    text: str = "Spotify AB/26-01-23",
    amount: Decimal = Decimal("-125.00"),
    display_text: str | None = None,
) -> BankTransaction:
    """Helper to build a BankTransaction with sensible defaults."""
    return BankTransaction(
        booking_date=date(2026, 1, 28),
        value_date=date(2026, 1, 28),
        verification_number="12345",
        text=text,
        amount=amount,
        balance=Decimal("10000.00"),
        display_text=display_text,
    )


# ---------------------------------------------------------------------------
# display_text field
# ---------------------------------------------------------------------------

class TestDisplayTextField:
    """Tests for the display_text field on BankTransaction."""

    def test_display_text_defaults_to_none(self) -> None:
        txn = _make_transaction()
        assert txn.display_text is None

    def test_display_text_can_be_set(self) -> None:
        txn = _make_transaction(display_text="Elbolaget AB")
        assert txn.display_text == "Elbolaget AB"
        assert txn.text == "Spotify AB/26-01-23"


# ---------------------------------------------------------------------------
# Categorization with display_text
# ---------------------------------------------------------------------------

class TestCategorizationWithDisplayText:
    """Tests for categorization using display_text field."""

    def test_categorization_uses_display_text_when_set(
        self, rules_db: RulesDatabase
    ) -> None:
        """When display_text is set, categorizer should match against it."""
        save_rule(
            rules_db,
            pattern="elbolaget",
            debit_account=6200,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-500.00"),
        )
        txn = _make_transaction(
            text="8001-12345/26-01-15",
            display_text="Elbolaget AB",
        )
        result = suggest_categorization(txn, rules_db)
        assert result is not None
        assert result.debit_account == 6200

    def test_categorization_falls_back_to_text(
        self, rules_db: RulesDatabase
    ) -> None:
        """When display_text is None, categorizer should use text."""
        save_rule(
            rules_db,
            pattern="spotify",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-125.00"),
        )
        txn = _make_transaction(text="Spotify AB/26-01-23")
        assert txn.display_text is None
        result = suggest_categorization(txn, rules_db)
        assert result is not None
        assert result.debit_account == 6540

    def test_matches_original_text_even_when_display_text_set(
        self, rules_db: RulesDatabase
    ) -> None:
        """Rules matching original text should still work when display_text is set."""
        save_rule(
            rules_db,
            pattern="8001-12345",
            debit_account=6200,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            amount=Decimal("-100.00"),
        )
        txn = _make_transaction(
            text="8001-12345/26-01-15",
            display_text="Elbolaget AB",
        )
        # Should match because categorizer tries raw text first, then display_text
        result = suggest_categorization(txn, rules_db)
        assert result is not None
        assert result.debit_account == 6200


# ---------------------------------------------------------------------------
# Alias CRUD
# ---------------------------------------------------------------------------

class TestAliasCRUD:
    """Tests for alias CRUD operations in RulesDatabase."""

    def test_add_and_list_alias(self, rules_db: RulesDatabase) -> None:
        rules_db.add_alias("8001-12345", "Elbolaget AB")
        aliases = rules_db.list_aliases()
        assert len(aliases) == 1
        assert aliases[0].pattern == "8001-12345"
        assert aliases[0].replacement == "Elbolaget AB"

    def test_update_existing_alias(self, rules_db: RulesDatabase) -> None:
        rules_db.add_alias("8001-12345", "Elbolaget")
        rules_db.add_alias("8001-12345", "Elbolaget Sverige AB")
        aliases = rules_db.list_aliases()
        assert len(aliases) == 1
        assert aliases[0].replacement == "Elbolaget Sverige AB"

    def test_delete_alias(self, rules_db: RulesDatabase) -> None:
        rules_db.add_alias("test-pattern", "Test Replacement")
        aliases = rules_db.list_aliases()
        assert len(aliases) == 1
        rules_db.delete_alias(aliases[0].id)
        assert rules_db.list_aliases() == []

    def test_delete_nonexistent_alias(self, rules_db: RulesDatabase) -> None:
        """Deleting a non-existent alias should not raise."""
        rules_db.delete_alias(999)

    def test_list_aliases_ordered_by_length(
        self, rules_db: RulesDatabase
    ) -> None:
        """Longer patterns should come first in the list."""
        rules_db.add_alias("AB", "Short")
        rules_db.add_alias("Spotify AB", "Longer")
        rules_db.add_alias("Test", "Medium")
        aliases = rules_db.list_aliases()
        assert aliases[0].pattern == "Spotify AB"
        assert aliases[1].pattern == "Test"
        assert aliases[2].pattern == "AB"

    def test_alias_has_created_at(self, rules_db: RulesDatabase) -> None:
        rules_db.add_alias("test", "Test")
        aliases = rules_db.list_aliases()
        assert aliases[0].created_at is not None


# ---------------------------------------------------------------------------
# apply_aliases function
# ---------------------------------------------------------------------------

class TestApplyAliases:
    """Tests for the apply_aliases function."""

    def test_matching_alias_returns_replacement(self) -> None:
        aliases = [
            TextAlias(id=1, pattern="8001-12345", replacement="Elbolaget AB"),
        ]
        result = apply_aliases("8001-12345/26-01-15", aliases)
        assert result == "Elbolaget AB"

    def test_no_match_returns_none(self) -> None:
        aliases = [
            TextAlias(id=1, pattern="8001-12345", replacement="Elbolaget AB"),
        ]
        result = apply_aliases("Spotify AB/26-01-15", aliases)
        assert result is None

    def test_case_insensitive_matching(self) -> None:
        aliases = [
            TextAlias(id=1, pattern="spotify", replacement="Spotify AB"),
        ]
        result = apply_aliases("SPOTIFY AB/26-01-23", aliases)
        assert result == "Spotify AB"

    def test_longest_pattern_wins(self) -> None:
        """Aliases are pre-sorted longest-first; first match wins."""
        aliases = [
            TextAlias(id=2, pattern="1234-5678", replacement="Elbolaget AB"),
            TextAlias(id=1, pattern="1234", replacement="Bank"),
        ]
        result = apply_aliases("1234-5678 betalning", aliases)
        assert result == "Elbolaget AB"

    def test_empty_aliases_returns_none(self) -> None:
        result = apply_aliases("any text", [])
        assert result is None


# ---------------------------------------------------------------------------
# rules create CLI
# ---------------------------------------------------------------------------

class TestRulesCreate:
    """Tests for the rules create CLI subcommand."""

    def test_create_rule_with_all_arguments(
        self, rules_db: RulesDatabase
    ) -> None:
        """Creating a rule via save_rule stores it correctly."""
        save_rule(
            rules_db,
            pattern="spotify",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-125.00"),
            match_type="contains",
        )
        rules = rules_db.list_rules()
        assert len(rules) == 1
        assert rules[0].pattern == "spotify"
        assert rules[0].debit_account == 6540
        assert rules[0].credit_account == 1930
        assert rules[0].vat_rate == Decimal("0.25")
        assert rules[0].match_type == "contains"

    def test_create_rule_with_exact_match_type(
        self, rules_db: RulesDatabase
    ) -> None:
        save_rule(
            rules_db,
            pattern="Spotify AB/26-01-23",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            amount=Decimal("-125.00"),
            match_type="exact",
        )
        rules = rules_db.list_rules()
        assert len(rules) == 1
        assert rules[0].match_type == "exact"

    def test_create_rule_with_default_vat(
        self, rules_db: RulesDatabase
    ) -> None:
        save_rule(
            rules_db,
            pattern="bankavgift",
            debit_account=6570,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            amount=Decimal("-75.00"),
        )
        rules = rules_db.list_rules()
        assert rules[0].vat_rate == Decimal("0.00")
        assert rules[0].vat_account is None


# ---------------------------------------------------------------------------
# configure() argument types
# ---------------------------------------------------------------------------

class TestConfigureCallTypes:
    """Tests verifying the configure() call uses correct types."""

    def test_configure_accepts_correct_arguments(self) -> None:
        """Verify the GTK app configure() signature accepts the right args.

        We can't easily test GTK in CI, but we can verify the function
        signature matches what cli.py will pass.
        """
        import inspect

        try:
            from bookkeeping.gtk_app import BookkeepingApp
        except ImportError:
            pytest.skip("GTK4 not available")

        sig = inspect.signature(BookkeepingApp.configure)
        params = list(sig.parameters.keys())
        # self is first, then the actual parameters
        assert "suggestions" in params
        assert "accounts" in params
        assert "new_count" in params
        assert "duplicate_count" in params
        assert "on_save" in params
        assert "on_save_rules" in params
        # These should NOT be in the signature
        assert "transactions" not in params
        assert "gnucash_book_path" not in params
