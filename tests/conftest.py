"""Shared pytest fixtures for the bokföring test suite."""

from datetime import date
from decimal import Decimal

import pytest

from bokforing.models import (
    BankTransaction,
    JournalEntry,
    JournalEntrySplit,
    Rule,
)


@pytest.fixture
def sample_bank_transaction() -> BankTransaction:
    """A typical expense transaction (Spotify subscription with 25% VAT)."""
    return BankTransaction(
        bokforingsdatum=date(2026, 1, 28),
        valutadatum=date(2026, 1, 28),
        verifikationsnummer="12345",
        text="Spotify",
        belopp=Decimal("-125.00"),
        saldo=Decimal("10000.00"),
    )


@pytest.fixture
def sample_income_transaction() -> BankTransaction:
    """A typical income transaction (consulting payment)."""
    return BankTransaction(
        bokforingsdatum=date(2026, 1, 15),
        valutadatum=date(2026, 1, 15),
        verifikationsnummer="12340",
        text="Kund AB betalning",
        belopp=Decimal("10000.00"),
        saldo=Decimal("20000.00"),
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
        verifikationsnummer="12345",
        datum=date(2026, 1, 28),
        beskrivning="Spotify",
        splits=[
            JournalEntrySplit(account_code=6540, amount=Decimal("100.00")),
            JournalEntrySplit(account_code=2640, amount=Decimal("25.00")),
            JournalEntrySplit(account_code=1930, amount=Decimal("-125.00")),
        ],
    )
