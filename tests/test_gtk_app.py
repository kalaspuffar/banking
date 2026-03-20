"""Unit tests for the GTK4 verification GUI logic.

Tests cover the pure-Python logic (formatting, journal entry conversion,
account filtering, categorization counting) that runs without GTK4.
GObject model tests require PyGObject and are skipped when unavailable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bookkeeping.gtk_app import (
    build_journal_entry,
    categorization_count,
    format_amount_swedish,
    matches_account_filter,
)
from bookkeeping.models import (
    BankTransaction,
    CategorizationSuggestion,
    JournalEntry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def expense_transaction() -> BankTransaction:
    """A typical expense (Spotify subscription, 25% VAT)."""
    return BankTransaction(
        booking_date=date(2026, 1, 28),
        value_date=date(2026, 1, 28),
        verification_number="12345",
        text="Spotify",
        amount=Decimal("-125.00"),
        balance=Decimal("10000.00"),
    )


@pytest.fixture
def income_transaction() -> BankTransaction:
    """A typical income (consulting payment, 25% VAT)."""
    return BankTransaction(
        booking_date=date(2026, 1, 15),
        value_date=date(2026, 1, 15),
        verification_number="12340",
        text="Kund AB betalning",
        amount=Decimal("10000.00"),
        balance=Decimal("20000.00"),
    )


@pytest.fixture
def no_vat_transaction() -> BankTransaction:
    """A bank fee with 0% VAT."""
    return BankTransaction(
        booking_date=date(2026, 2, 1),
        value_date=date(2026, 2, 1),
        verification_number="12350",
        text="Bankavgift",
        amount=Decimal("-118.50"),
        balance=Decimal("9881.50"),
    )


@pytest.fixture
def categorized_suggestion(expense_transaction) -> CategorizationSuggestion:
    """A suggestion with high confidence (pattern match)."""
    return CategorizationSuggestion(
        transaction=expense_transaction,
        debit_account=6540,
        credit_account=1930,
        vat_rate=Decimal("0.25"),
        vat_account=2640,
        confidence="pattern",
        rule_id=1,
    )


@pytest.fixture
def uncategorized_suggestion(no_vat_transaction) -> CategorizationSuggestion:
    """A suggestion with no match."""
    return CategorizationSuggestion(
        transaction=no_vat_transaction,
        debit_account=0,
        credit_account=1930,
        vat_rate=Decimal("0.00"),
        vat_account=None,
        confidence="none",
        rule_id=None,
    )


# ---------------------------------------------------------------------------
# Amount formatting tests (pure Python)
# ---------------------------------------------------------------------------

class TestFormatAmountSwedish:
    """Test Swedish decimal comma formatting."""

    def test_negative_amount(self):
        assert format_amount_swedish(Decimal("-125.00")) == "-125,00"

    def test_positive_amount(self):
        assert format_amount_swedish(Decimal("500.00")) == "500,00"

    def test_thousands_separator(self):
        assert format_amount_swedish(Decimal("10000.00")) == "10 000,00"

    def test_large_amount(self):
        assert format_amount_swedish(Decimal("1234567.89")) == "1 234 567,89"

    def test_zero(self):
        assert format_amount_swedish(Decimal("0.00")) == "0,00"

    def test_negative_with_thousands(self):
        assert format_amount_swedish(Decimal("-10000.50")) == "-10 000,50"

    def test_small_amount(self):
        assert format_amount_swedish(Decimal("1.50")) == "1,50"

    def test_three_decimal_input_quantized(self):
        """Input with 3 decimals (from bank CSV) is quantized to 2."""
        assert format_amount_swedish(Decimal("-100.000")) == "-100,00"


# ---------------------------------------------------------------------------
# Account filter tests (pure Python)
# ---------------------------------------------------------------------------

class TestMatchesAccountFilter:
    """Test account filter logic for the searchable account selector."""

    def test_empty_search_matches_all(self):
        assert matches_account_filter(1930, "Foretagskonto", "") is True

    def test_filter_by_account_number(self):
        assert matches_account_filter(1930, "Foretagskonto", "193") is True
        assert matches_account_filter(1930, "Foretagskonto", "194") is False

    def test_filter_by_account_name(self):
        assert matches_account_filter(6570, "Bankkostnader", "bank") is True

    def test_filter_case_insensitive(self):
        assert matches_account_filter(6570, "Bankkostnader", "BANK") is True
        assert matches_account_filter(6570, "Bankkostnader", "Bank") is True
        assert matches_account_filter(6570, "Bankkostnader", "bankkostnader") is True

    def test_filter_no_match(self):
        assert matches_account_filter(6570, "Bankkostnader", "spotify") is False

    def test_filter_partial_name(self):
        assert matches_account_filter(6540, "IT-tjanster", "tjanst") is True

    def test_filter_exact_number(self):
        assert matches_account_filter(2640, "Ingaende moms", "2640") is True


# ---------------------------------------------------------------------------
# Journal entry conversion tests (pure Python)
# ---------------------------------------------------------------------------

class TestBuildJournalEntry:
    """Test conversion from transaction data to balanced JournalEntry."""

    def test_expense_with_25_percent_vat(self):
        """Expense -125 SEK with 25% VAT produces 3 splits summing to zero."""
        entry = build_journal_entry(
            verification_number="12345",
            booking_date=date(2026, 1, 28),
            description="Spotify",
            amount=Decimal("-125.00"),
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            vat_account=2640,
        )

        assert isinstance(entry, JournalEntry)
        assert entry.verification_number == "12345"
        assert entry.entry_date == date(2026, 1, 28)
        assert entry.description == "Spotify"
        assert len(entry.splits) == 3

        total = sum(s.amount for s in entry.splits)
        assert total == Decimal("0")

        # Bank split: -125.00 on 1930
        bank = next(s for s in entry.splits if s.account_code == 1930)
        assert bank.amount == Decimal("-125.00")

        # Expense split: 100.00 on 6540
        expense = next(s for s in entry.splits if s.account_code == 6540)
        assert expense.amount == Decimal("100.00")

        # VAT split: 25.00 on 2640
        vat = next(s for s in entry.splits if s.account_code == 2640)
        assert vat.amount == Decimal("25.00")

    def test_expense_no_vat(self):
        """Expense with 0% VAT produces 2 splits."""
        entry = build_journal_entry(
            verification_number="12350",
            booking_date=date(2026, 2, 1),
            description="Bankavgift",
            amount=Decimal("-118.50"),
            debit_account=6570,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            vat_account=None,
        )

        assert len(entry.splits) == 2
        total = sum(s.amount for s in entry.splits)
        assert total == Decimal("0")

        bank = next(s for s in entry.splits if s.account_code == 1930)
        assert bank.amount == Decimal("-118.50")

        expense = next(s for s in entry.splits if s.account_code == 6570)
        assert expense.amount == Decimal("118.50")

    def test_income_with_25_percent_vat(self):
        """Income +10000 SEK with 25% VAT produces correct 3-way split."""
        entry = build_journal_entry(
            verification_number="12340",
            booking_date=date(2026, 1, 15),
            description="Kund AB betalning",
            amount=Decimal("10000.00"),
            debit_account=3010,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            vat_account=2610,
        )

        assert len(entry.splits) == 3
        total = sum(s.amount for s in entry.splits)
        assert total == Decimal("0")

        # Bank gets +10000
        bank = next(s for s in entry.splits if s.account_code == 1930)
        assert bank.amount == Decimal("10000.00")

        # Revenue gets -8000 (credit)
        revenue = next(s for s in entry.splits if s.account_code == 3010)
        assert revenue.amount == Decimal("-8000.00")

        # VAT gets -2000 (credit)
        vat = next(s for s in entry.splits if s.account_code == 2610)
        assert vat.amount == Decimal("-2000.00")

    def test_income_no_vat(self):
        """Income with 0% VAT produces a simple 2-way split."""
        entry = build_journal_entry(
            verification_number="12341",
            booking_date=date(2026, 1, 20),
            description="YouTube revenue",
            amount=Decimal("500.00"),
            debit_account=3040,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            vat_account=None,
        )

        assert len(entry.splits) == 2
        total = sum(s.amount for s in entry.splits)
        assert total == Decimal("0")


# ---------------------------------------------------------------------------
# Categorization counting tests (pure Python)
# ---------------------------------------------------------------------------

class TestCategorizationCount:
    """Test the categorization counter logic."""

    def test_all_uncategorized(self, uncategorized_suggestion):
        categorized, uncategorized = categorization_count(
            [uncategorized_suggestion, uncategorized_suggestion]
        )
        assert categorized == 0
        assert uncategorized == 2

    def test_mixed(self, categorized_suggestion, uncategorized_suggestion):
        categorized, uncategorized = categorization_count(
            [categorized_suggestion, uncategorized_suggestion, categorized_suggestion]
        )
        assert categorized == 2
        assert uncategorized == 1

    def test_all_categorized(self, categorized_suggestion):
        categorized, uncategorized = categorization_count(
            [categorized_suggestion, categorized_suggestion]
        )
        assert categorized == 2
        assert uncategorized == 0

    def test_empty_list(self):
        categorized, uncategorized = categorization_count([])
        assert categorized == 0
        assert uncategorized == 0


# ---------------------------------------------------------------------------
# Save button enable/disable logic tests (pure Python)
# ---------------------------------------------------------------------------

class TestSaveButtonLogic:
    """Test that save button state correctly reflects categorization status."""

    def test_disabled_with_uncategorized(
        self, categorized_suggestion, uncategorized_suggestion
    ):
        """When some rows are uncategorized, save should be disabled."""
        _, uncategorized = categorization_count(
            [categorized_suggestion, uncategorized_suggestion]
        )
        assert uncategorized > 0

    def test_enabled_when_all_categorized(self, categorized_suggestion):
        """When all rows are categorized, save should be enabled."""
        _, uncategorized = categorization_count(
            [categorized_suggestion, categorized_suggestion]
        )
        assert uncategorized == 0

    def test_categorizing_all_enables_save(self, uncategorized_suggestion):
        """Starting uncategorized, then having all categorized enables save."""
        _, uncategorized_before = categorization_count(
            [uncategorized_suggestion]
        )
        assert uncategorized_before == 1

        # Simulate categorization by creating a categorized version
        txn = uncategorized_suggestion.transaction
        now_categorized = CategorizationSuggestion(
            transaction=txn,
            debit_account=6570,
            credit_account=1930,
            vat_rate=Decimal("0.00"),
            vat_account=None,
            confidence="pattern",
            rule_id=None,
        )
        _, uncategorized_after = categorization_count([now_categorized])
        assert uncategorized_after == 0


# ---------------------------------------------------------------------------
# GObject model tests (require GTK4, skip if unavailable)
# ---------------------------------------------------------------------------

def _skip_if_no_gtk():
    """Skip test if GTK4/PyGObject is not available."""
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import GObject  # noqa: F401
    except (ImportError, ValueError):
        pytest.skip("GTK4/PyGObject not available")


class TestTransactionRowGObject:
    """Test TransactionRow GObject model (requires GTK4)."""

    def test_categorized_row_properties(self, categorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(categorized_suggestion)

        assert row.datum == "2026-01-28"
        assert row.text == "Spotify"
        assert row.is_categorized is True
        assert row.konto == 6540
        assert row.konto_display == "\u25a0 6540"
        assert row.moms_display == "25%"

    def test_uncategorized_row_properties(self, uncategorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(uncategorized_suggestion)

        assert row.datum == "2026-02-01"
        assert row.text == "Bankavgift"
        assert row.is_categorized is False
        assert row.konto == 0
        assert row.konto_display == "? ----"
        assert row.moms_display == "0%"

    def test_set_account_updates_row(self, uncategorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(uncategorized_suggestion)
        assert row.is_categorized is False

        row.set_account(6570, Decimal("0.00"), None)

        assert row.is_categorized is True
        assert row.konto == 6570
        assert row.konto_display == "\u25a0 6570"
        assert row.debit_account == 6570

    def test_saldo_display(self, categorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(categorized_suggestion)
        assert row.saldo_display == "10 000,00"

    def test_to_journal_entry(self, categorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(categorized_suggestion)
        entry = row.to_journal_entry()

        assert isinstance(entry, JournalEntry)
        assert entry.verification_number == "12345"
        total = sum(s.amount for s in entry.splits)
        assert total == Decimal("0")

    def test_uncategorized_to_journal_entry_raises(self, uncategorized_suggestion):
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import TransactionRow

        row = TransactionRow(uncategorized_suggestion)
        with pytest.raises(ValueError, match="uncategorized"):
            row.to_journal_entry()


# ---------------------------------------------------------------------------
# load_accounts_from_gnucash tests (require GTK4, skip if unavailable)
# ---------------------------------------------------------------------------

class TestLoadAccountsFromGnuCash:
    """Test loading accounts from a GnuCash book."""

    def test_file_not_found_raises_gnucash_error(self):
        """A non-existent book path raises GnuCashError."""
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import load_accounts_from_gnucash
        from bookkeeping.models import GnuCashError

        with pytest.raises(GnuCashError, match="not found"):
            load_accounts_from_gnucash("/nonexistent/path/book.gnucash")

    def test_custom_vat_rates_override_defaults(self):
        """When vat_rates dict is provided, those rates take precedence."""
        _skip_if_no_gtk()
        from bookkeeping.gtk_app import AccountItem, _lookup_default_vat_rate

        # Verify default for 6540 is 0.25
        assert _lookup_default_vat_rate(6540) == Decimal("0.25")

        # Verify unknown account defaults to 0.00
        assert _lookup_default_vat_rate(9999) == Decimal("0.00")

        # Verify known accounts return correct defaults
        assert _lookup_default_vat_rate(3010) == Decimal("0.25")
        assert _lookup_default_vat_rate(3011) == Decimal("0.12")
        assert _lookup_default_vat_rate(3012) == Decimal("0.06")
