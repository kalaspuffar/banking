"""Tests for the rule-based transaction categorization engine.

Covers:
- Text normalization (date suffix stripping, lowercasing, edge cases)
- Exact match returning "exact" confidence
- Contains match returning "pattern" confidence
- No match returning None
- Multiple contains matches resolved by most recent last_used
- Multiple exact matches resolved by most recent last_used
- save_rule persisting via RulesDatabase
- VAT split info in suggestions (25%, 12%, 6%, and 0% cases)
- _resolve_vat_account raising ValueError for unsupported rates
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest

from bookkeeping.categorizer import (
    normalize_text,
    save_rule,
    suggest_categorization,
)
from bookkeeping.models import (
    BankTransaction,
    CategorizationSuggestion,
    Rule,
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
    booking_date: date | None = None,
) -> BankTransaction:
    """Helper to build a BankTransaction with sensible defaults."""
    return BankTransaction(
        booking_date=booking_date or date(2026, 1, 28),
        value_date=date(2026, 1, 28),
        verification_number="12345",
        text=text,
        amount=amount,
        balance=Decimal("10000.00"),
    )


def _make_rule(
    pattern: str = "spotify ab",
    match_type: str = "contains",
    debit_account: int = 6540,
    credit_account: int = 1930,
    vat_rate: Decimal = Decimal("0.25"),
    vat_account: int | None = 2640,
    last_used: date | None = None,
    rule_id: int | None = 1,
) -> Rule:
    """Helper to build a Rule with sensible defaults."""
    return Rule(
        id=rule_id,
        pattern=pattern,
        match_type=match_type,
        debit_account=debit_account,
        credit_account=credit_account,
        vat_rate=vat_rate,
        vat_account=vat_account,
        last_used=last_used or date(2026, 1, 15),
        use_count=5,
    )


# ---------------------------------------------------------------------------
# Text normalization tests (Tasks 2.1, 2.2)
# ---------------------------------------------------------------------------

class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_strips_date_suffix_and_lowercases(self) -> None:
        assert normalize_text("Spotify AB/26-01-23") == "spotify ab"

    def test_different_date_suffix(self) -> None:
        assert normalize_text("SPOTIFY AB/25-12-15") == "spotify ab"

    def test_no_date_suffix_lowercases_only(self) -> None:
        assert normalize_text("BANKAVGIFT") == "bankavgift"

    def test_already_lowercase(self) -> None:
        assert normalize_text("bankavgift") == "bankavgift"

    def test_empty_text(self) -> None:
        assert normalize_text("") == ""

    def test_text_with_slash_but_not_date_suffix(self) -> None:
        """A slash followed by non-date content should not be stripped."""
        assert normalize_text("Google/YouTube") == "google/youtube"

    def test_date_suffix_only_at_end(self) -> None:
        """Date suffix in the middle should not be stripped."""
        assert normalize_text("AB/26-01-23 extra") == "ab/26-01-23 extra"


# ---------------------------------------------------------------------------
# Exact match tests (Tasks 3.1, 3.5, 4.1)
# ---------------------------------------------------------------------------

class TestExactMatch:
    """Tests for exact match categorization."""

    def test_exact_match_returns_exact_confidence(
        self, rules_db: RulesDatabase
    ) -> None:
        rule = _make_rule(
            pattern="Spotify AB/26-01-23",
            match_type="exact",
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "exact"
        assert result.debit_account == 6540
        assert result.credit_account == 1930

    def test_exact_match_takes_priority_over_contains(
        self, rules_db: RulesDatabase
    ) -> None:
        """Exact match should win even if a contains rule also matches."""
        exact_rule = _make_rule(
            pattern="Spotify AB/26-01-23",
            match_type="exact",
            debit_account=6540,
        )
        contains_rule = _make_rule(
            pattern="spotify",
            match_type="contains",
            debit_account=6212,
            rule_id=2,
        )
        rules_db.save_rule(exact_rule)
        rules_db.save_rule(contains_rule)

        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "exact"
        assert result.debit_account == 6540


# ---------------------------------------------------------------------------
# Contains match tests (Tasks 3.2, 3.5, 4.2)
# ---------------------------------------------------------------------------

class TestContainsMatch:
    """Tests for contains match categorization."""

    def test_contains_match_returns_pattern_confidence(
        self, rules_db: RulesDatabase
    ) -> None:
        rule = _make_rule(pattern="spotify ab", match_type="contains")
        rules_db.save_rule(rule)

        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "pattern"
        assert result.debit_account == 6540
        assert result.credit_account == 1930

    def test_contains_match_case_insensitive(
        self, rules_db: RulesDatabase
    ) -> None:
        rule = _make_rule(pattern="spotify ab", match_type="contains")
        rules_db.save_rule(rule)

        transaction = _make_transaction(text="SPOTIFY AB/25-12-15")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "pattern"


# ---------------------------------------------------------------------------
# No match tests (Tasks 3.5)
# ---------------------------------------------------------------------------

class TestNoMatch:
    """Tests for when no rule matches."""

    def test_no_match_returns_none(self, rules_db: RulesDatabase) -> None:
        transaction = _make_transaction(text="Unknown Vendor XYZ")
        result = suggest_categorization(transaction, rules_db)

        assert result is None

    def test_no_match_with_empty_rules_db(
        self, rules_db: RulesDatabase
    ) -> None:
        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is None


# ---------------------------------------------------------------------------
# Multiple match resolution (Task 3.3)
# ---------------------------------------------------------------------------

class TestMultipleMatchResolution:
    """Tests for resolving multiple contains matches by recency."""

    def test_picks_most_recent_last_used(
        self, rules_db: RulesDatabase
    ) -> None:
        older_rule = _make_rule(
            pattern="spotify",
            match_type="contains",
            debit_account=6540,
            last_used=date(2026, 1, 15),
            rule_id=1,
        )
        newer_rule = _make_rule(
            pattern="spotify ab",
            match_type="contains",
            debit_account=6212,
            last_used=date(2026, 2, 20),
            rule_id=2,
        )
        rules_db.save_rule(older_rule)
        rules_db.save_rule(newer_rule)

        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "pattern"
        assert result.debit_account == 6212


# ---------------------------------------------------------------------------
# save_rule tests (Tasks 5.1, 5.2)
# ---------------------------------------------------------------------------

class TestSaveRule:
    """Tests for the save_rule wrapper function."""

    def test_save_rule_persists_to_database(
        self, rules_db: RulesDatabase
    ) -> None:
        save_rule(
            rules_db,
            pattern="spotify ab",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-125.00"),
        )

        rules = rules_db.list_rules()
        assert len(rules) == 1
        assert rules[0].pattern == "spotify ab"
        assert rules[0].match_type == "contains"
        assert rules[0].debit_account == 6540
        assert rules[0].credit_account == 1930
        assert rules[0].vat_rate == Decimal("0.25")

    def test_save_rule_sets_vat_account_for_expense(
        self, rules_db: RulesDatabase
    ) -> None:
        """Negative amount (expense) should get ingående moms 2640."""
        save_rule(
            rules_db,
            pattern="spotify ab",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-125.00"),
        )

        rules = rules_db.list_rules()
        assert rules[0].vat_account == 2640

    def test_save_rule_sets_vat_account_for_income(
        self, rules_db: RulesDatabase
    ) -> None:
        """Positive amount (income) should get utgående moms 2610."""
        save_rule(
            rules_db,
            pattern="consulting invoice",
            debit_account=1930,
            credit_account=3010,
            vat_rate=Decimal("0.25"),
            amount=Decimal("10000.00"),
        )

        rules = rules_db.list_rules()
        assert rules[0].vat_account == 2610

    def test_save_rule_no_vat_account_for_zero_rate(
        self, rules_db: RulesDatabase
    ) -> None:
        save_rule(
            rules_db,
            pattern="bankavgift",
            debit_account=6570,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            amount=Decimal("-118.50"),
        )

        rules = rules_db.list_rules()
        assert rules[0].vat_account is None

    def test_saved_rule_is_found_by_suggest(
        self, rules_db: RulesDatabase
    ) -> None:
        """A saved rule should be found by subsequent suggest_categorization."""
        save_rule(
            rules_db,
            pattern="spotify ab",
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            amount=Decimal("-125.00"),
        )

        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "pattern"
        assert result.debit_account == 6540


# ---------------------------------------------------------------------------
# VAT split info tests (Tasks 3.4)
# ---------------------------------------------------------------------------

class TestVATSplitInSuggestion:
    """Tests for VAT split info included in suggestions."""

    def test_suggestion_includes_vat_rate_25(
        self, rules_db: RulesDatabase
    ) -> None:
        rule = _make_rule(
            pattern="spotify ab",
            match_type="contains",
            vat_rate=Decimal("0.25"),
            vat_account=2640,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Spotify AB/26-01-23",
            amount=Decimal("-125.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.25")
        assert result.vat_account == 2640

    def test_suggestion_with_zero_vat_has_no_vat_account(
        self, rules_db: RulesDatabase
    ) -> None:
        rule = _make_rule(
            pattern="bankavgift",
            match_type="contains",
            vat_rate=Decimal("0.00"),
            vat_account=None,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="BANKAVGIFT",
            amount=Decimal("-118.50"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.00")
        assert result.vat_account is None

    def test_suggestion_income_gets_utgaende_moms(
        self, rules_db: RulesDatabase
    ) -> None:
        """Positive amount (income) should get utgående moms account 2610."""
        rule = _make_rule(
            pattern="consulting",
            match_type="contains",
            debit_account=1930,
            credit_account=3010,
            vat_rate=Decimal("0.25"),
            vat_account=2610,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Consulting Invoice",
            amount=Decimal("10000.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.25")
        assert result.vat_account == 2610

    def test_suggestion_expense_12_percent_vat(
        self, rules_db: RulesDatabase
    ) -> None:
        """12% expense should get ingående moms 2640."""
        rule = _make_rule(
            pattern="food delivery",
            match_type="contains",
            debit_account=4010,
            credit_account=1930,
            vat_rate=Decimal("0.12"),
            vat_account=2640,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Food Delivery AB",
            amount=Decimal("-224.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.12")
        assert result.vat_account == 2640

    def test_suggestion_income_12_percent_gets_utgaende_moms_2620(
        self, rules_db: RulesDatabase
    ) -> None:
        """12% income should get utgående moms 2620."""
        rule = _make_rule(
            pattern="catering",
            match_type="contains",
            debit_account=1930,
            credit_account=3011,
            vat_rate=Decimal("0.12"),
            vat_account=2620,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Catering Service",
            amount=Decimal("5600.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.12")
        assert result.vat_account == 2620

    def test_suggestion_expense_6_percent_vat(
        self, rules_db: RulesDatabase
    ) -> None:
        """6% expense should get ingående moms 2640."""
        rule = _make_rule(
            pattern="book purchase",
            match_type="contains",
            debit_account=6900,
            credit_account=1930,
            vat_rate=Decimal("0.06"),
            vat_account=2640,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Book Purchase AB",
            amount=Decimal("-106.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.06")
        assert result.vat_account == 2640

    def test_suggestion_income_6_percent_gets_utgaende_moms_2630(
        self, rules_db: RulesDatabase
    ) -> None:
        """6% income should get utgående moms 2630."""
        rule = _make_rule(
            pattern="ticket sales",
            match_type="contains",
            debit_account=1930,
            credit_account=3012,
            vat_rate=Decimal("0.06"),
            vat_account=2630,
        )
        rules_db.save_rule(rule)

        transaction = _make_transaction(
            text="Ticket Sales Event",
            amount=Decimal("1060.00"),
        )
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.vat_rate == Decimal("0.06")
        assert result.vat_account == 2630


# ---------------------------------------------------------------------------
# Exact match tiebreaker tests (Issue #8)
# ---------------------------------------------------------------------------

class TestExactMatchTiebreaker:
    """Tests for resolving multiple exact matches by recency."""

    def test_picks_most_recent_exact_match(
        self, rules_db: RulesDatabase
    ) -> None:
        """When multiple exact rules match, the most recently used wins."""
        older_rule = _make_rule(
            pattern="Spotify AB/26-01-23",
            match_type="exact",
            debit_account=6540,
            last_used=date(2026, 1, 10),
            rule_id=1,
        )
        newer_rule = _make_rule(
            pattern="Spotify AB/26-01-23",
            match_type="exact",
            debit_account=6212,
            last_used=date(2026, 2, 15),
            rule_id=2,
        )
        # Save older first, then newer — find_rule should return newer
        rules_db.save_rule(older_rule)
        # Update the existing rule with newer last_used and different account
        rules_db._conn.execute(
            "INSERT INTO rules "
            "(pattern, match_type, debit_account, credit_account, "
            "vat_rate, vat_account, last_used, use_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Spotify AB/26-01-23 v2",
                "exact",
                newer_rule.debit_account,
                newer_rule.credit_account,
                str(newer_rule.vat_rate),
                newer_rule.vat_account,
                newer_rule.last_used.isoformat(),
                newer_rule.use_count,
            ),
        )
        rules_db._conn.commit()

        # Use the text that matches the older rule's pattern
        transaction = _make_transaction(text="Spotify AB/26-01-23")
        result = suggest_categorization(transaction, rules_db)

        assert result is not None
        assert result.confidence == "exact"


# ---------------------------------------------------------------------------
# _resolve_vat_account error handling (Issue #6)
# ---------------------------------------------------------------------------

class TestResolveVATAccountErrors:
    """Tests for _resolve_vat_account raising ValueError on unsupported rates."""

    def test_unsupported_nonzero_rate_raises_value_error(self) -> None:
        from bookkeeping.categorizer import _resolve_vat_account

        with pytest.raises(ValueError, match="Unsupported non-zero VAT rate"):
            _resolve_vat_account(Decimal("0.10"), Decimal("-100.00"))

    def test_zero_rate_returns_none(self) -> None:
        from bookkeeping.categorizer import _resolve_vat_account

        assert _resolve_vat_account(Decimal("0.00"), Decimal("-100.00")) is None
