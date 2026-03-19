"""Shared pytest fixtures for the bookkeeping test suite."""

from datetime import date
from decimal import Decimal

import pytest

from bookkeeping.models import (
    BankTransaction,
    JournalEntry,
    JournalEntrySplit,
    Rule,
)


@pytest.fixture
def sample_bank_transaction() -> BankTransaction:
    """A typical expense transaction (Spotify subscription with 25% VAT)."""
    return BankTransaction(
        booking_date=date(2026, 1, 28),
        value_date=date(2026, 1, 28),
        verification_number="12345",
        text="Spotify",
        amount=Decimal("-125.00"),
        balance=Decimal("10000.00"),
    )


@pytest.fixture
def sample_income_transaction() -> BankTransaction:
    """A typical income transaction (consulting payment)."""
    return BankTransaction(
        booking_date=date(2026, 1, 15),
        value_date=date(2026, 1, 15),
        verification_number="12340",
        text="Kund AB betalning",
        amount=Decimal("10000.00"),
        balance=Decimal("20000.00"),
    )


@pytest.fixture
def sample_bank_transaction_3_decimal() -> BankTransaction:
    """A transaction with 3-decimal amount matching real bank CSV format.

    The bank CSV exports amounts like -100.000 which, after parsing to
    Decimal, preserves trailing precision. This fixture validates that
    the model handles such values correctly.
    """
    return BankTransaction(
        booking_date=date(2026, 2, 1),
        value_date=date(2026, 2, 1),
        verification_number="12350",
        text="Bankavgift",
        amount=Decimal("-100.000"),
        balance=Decimal("9900.000"),
    )


@pytest.fixture
def sample_rule() -> Rule:
    """A categorization rule for Spotify subscriptions."""
    return Rule(
        id=1,
        pattern="Spotify",
        match_type="contains",
        debit_account=6540,
        credit_account=1930,
        vat_rate=Decimal("0.25"),
        vat_account=2640,
        last_used=date(2026, 1, 28),
        use_count=3,
    )


@pytest.fixture
def sample_journal_entry() -> JournalEntry:
    """A balanced journal entry for a software subscription with 25% VAT.

    Spotify -125 SEK: expense 100 (debit 6540), VAT 25 (debit 2640),
    bank -125 (credit 1930).
    """
    return JournalEntry(
        verification_number="12345",
        entry_date=date(2026, 1, 28),
        description="Spotify",
        splits=[
            JournalEntrySplit(account_code=6540, amount=Decimal("100.00")),
            JournalEntrySplit(account_code=2640, amount=Decimal("25.00")),
            JournalEntrySplit(account_code=1930, amount=Decimal("-125.00")),
        ],
    )
