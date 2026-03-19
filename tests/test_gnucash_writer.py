"""Tests for bookkeeping.gnucash_writer.

Each test creates a temporary GnuCash book via piecash with SEK currency
and the BAS accounts needed for the scenarios, then exercises the writer
and verifies outcomes.
"""

from __future__ import annotations

import filecmp
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import piecash
import pytest

from bookkeeping.gnucash_writer import write_transactions
from bookkeeping.models import (
    GnuCashError,
    ImportResult,
    JournalEntry,
    JournalEntrySplit,
)

# BAS account codes used in tests
_ACCOUNT_CODES = {
    1930: "Företagskonto",
    3010: "Försäljning tjänster 25%",
    2610: "Utgående moms 25%",
    2640: "Ingående moms",
    6540: "IT-tjänster",
}


@pytest.fixture()
def gnucash_book(tmp_path: Path) -> Path:
    """Create a minimal GnuCash book with SEK and the required BAS accounts."""
    book_path = tmp_path / "test.gnucash"

    book = piecash.create_book(
        str(book_path),
        currency="SEK",
        overwrite=True,
    )

    with book:
        for code, name in _ACCOUNT_CODES.items():
            # Determine account type from BAS code range
            if 1000 <= code < 2000:
                account_type = "ASSET"
            elif 2000 <= code < 3000:
                account_type = "LIABILITY"
            elif 3000 <= code < 4000:
                account_type = "INCOME"
            else:
                account_type = "EXPENSE"

            piecash.Account(
                name=name,
                type=account_type,
                commodity=book.default_currency,
                parent=book.root_account,
                code=str(code),
            )

        book.save()

    return book_path


# ------------------------------------------------------------------
# 4.2 — Single 2-split transaction
# ------------------------------------------------------------------

class TestWriteSingleTransaction:
    """Write a single 2-split transaction and verify correctness."""

    def test_single_transaction_written(self, gnucash_book: Path) -> None:
        entry = JournalEntry(
            verification_number="10001",
            entry_date=date(2026, 1, 28),
            description="Consulting invoice",
            splits=(
                JournalEntrySplit(account_code=1930, amount=Decimal("10000.00")),
                JournalEntrySplit(account_code=3010, amount=Decimal("-10000.00")),
            ),
        )

        result = write_transactions(gnucash_book, [entry])

        assert result.transactions_written == 1
        assert result.errors == ()

        with piecash.open_book(str(gnucash_book), readonly=True) as book:
            txns = [
                t for t in book.transactions if t.num == "10001"
            ]
            assert len(txns) == 1

            txn = txns[0]
            assert txn.post_date == date(2026, 1, 28)
            assert txn.description == "Consulting invoice"
            assert txn.num == "10001"

            assert len(txn.splits) == 2
            amounts = {s.account.code: s.value for s in txn.splits}
            assert amounts["1930"] == Decimal("10000.00")
            assert amounts["3010"] == Decimal("-10000.00")


# ------------------------------------------------------------------
# 4.3 — 3-split transaction (expense + VAT)
# ------------------------------------------------------------------

class TestWriteThreeSplitTransaction:
    """Write a 3-split transaction with VAT and verify balance."""

    def test_three_split_balanced(self, gnucash_book: Path) -> None:
        entry = JournalEntry(
            verification_number="10002",
            entry_date=date(2026, 2, 15),
            description="Spotify subscription",
            splits=(
                JournalEntrySplit(account_code=1930, amount=Decimal("-125.00")),
                JournalEntrySplit(account_code=6540, amount=Decimal("100.00")),
                JournalEntrySplit(account_code=2640, amount=Decimal("25.00")),
            ),
        )

        result = write_transactions(gnucash_book, [entry])
        assert result.transactions_written == 1

        with piecash.open_book(str(gnucash_book), readonly=True) as book:
            txns = [t for t in book.transactions if t.num == "10002"]
            assert len(txns) == 1

            split_total = sum(s.value for s in txns[0].splits)
            assert split_total == Decimal("0")

            assert len(txns[0].splits) == 3


# ------------------------------------------------------------------
# 4.4 — Multiple transactions in one call
# ------------------------------------------------------------------

class TestWriteMultipleTransactions:
    """Write multiple transactions in a single call."""

    def test_multiple_all_committed(self, gnucash_book: Path) -> None:
        entries = [
            JournalEntry(
                verification_number=f"2000{i}",
                entry_date=date(2026, 3, i),
                description=f"Transaction {i}",
                splits=(
                    JournalEntrySplit(account_code=1930, amount=Decimal("500.00")),
                    JournalEntrySplit(account_code=3010, amount=Decimal("-500.00")),
                ),
            )
            for i in range(1, 4)
        ]

        result = write_transactions(gnucash_book, entries)
        assert result.transactions_written == 3

        with piecash.open_book(str(gnucash_book), readonly=True) as book:
            nums = {t.num for t in book.transactions}
            assert {"20001", "20002", "20003"}.issubset(nums)


# ------------------------------------------------------------------
# 4.5 — Non-existent account code → rollback
# ------------------------------------------------------------------

class TestAtomicRollback:
    """A bad account code rolls back all transactions."""

    def test_bad_code_raises_and_rolls_back(self, gnucash_book: Path) -> None:
        entries = [
            JournalEntry(
                verification_number="30001",
                entry_date=date(2026, 4, 1),
                description="Good entry",
                splits=(
                    JournalEntrySplit(account_code=1930, amount=Decimal("100.00")),
                    JournalEntrySplit(account_code=3010, amount=Decimal("-100.00")),
                ),
            ),
            JournalEntry(
                verification_number="30002",
                entry_date=date(2026, 4, 2),
                description="Bad entry — account 9999 does not exist",
                splits=(
                    JournalEntrySplit(account_code=1930, amount=Decimal("200.00")),
                    JournalEntrySplit(account_code=9999, amount=Decimal("-200.00")),
                ),
            ),
        ]

        with pytest.raises(GnuCashError, match="9999"):
            write_transactions(gnucash_book, entries)

        # Verify nothing was written
        with piecash.open_book(str(gnucash_book), readonly=True) as book:
            nums = {t.num for t in book.transactions}
            assert "30001" not in nums
            assert "30002" not in nums


# ------------------------------------------------------------------
# 4.6 — Non-existent book path
# ------------------------------------------------------------------

class TestNonExistentBook:
    """Writing to a missing book raises GnuCashError."""

    def test_missing_book_raises(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "does_not_exist.gnucash"
        entry = JournalEntry(
            verification_number="99999",
            entry_date=date(2026, 1, 1),
            description="Should fail",
            splits=(
                JournalEntrySplit(account_code=1930, amount=Decimal("50.00")),
                JournalEntrySplit(account_code=3010, amount=Decimal("-50.00")),
            ),
        )

        with pytest.raises(GnuCashError, match="not found"):
            write_transactions(fake_path, [entry])


# ------------------------------------------------------------------
# 4.7 — Backup creation and fidelity
# ------------------------------------------------------------------

class TestBackup:
    """Backup file is created before writing and is a faithful copy."""

    def test_backup_created_and_matches_original(
        self, gnucash_book: Path, tmp_path: Path
    ) -> None:
        # Take a reference copy of the original book before writing
        reference_copy = tmp_path / "reference.gnucash"
        shutil.copy2(gnucash_book, reference_copy)

        entry = JournalEntry(
            verification_number="40001",
            entry_date=date(2026, 5, 1),
            description="Backup test",
            splits=(
                JournalEntrySplit(account_code=1930, amount=Decimal("300.00")),
                JournalEntrySplit(account_code=3010, amount=Decimal("-300.00")),
            ),
        )

        write_transactions(gnucash_book, [entry])

        # Find the backup file
        backups = sorted(gnucash_book.parent.glob(f"{gnucash_book.name}.backup.*"))
        assert len(backups) >= 1, "No backup file was created"

        # The backup should match the original (pre-write) content
        assert filecmp.cmp(backups[-1], reference_copy, shallow=False)


# ------------------------------------------------------------------
# 4.8 — Empty entries list
# ------------------------------------------------------------------

class TestEmptyEntries:
    """Calling write_transactions with no entries returns immediately."""

    def test_empty_list_returns_zero(self, gnucash_book: Path) -> None:
        result = write_transactions(gnucash_book, [])

        assert result == ImportResult(transactions_written=0)

        # No backup should have been created
        backups = list(gnucash_book.parent.glob(f"{gnucash_book.name}.backup.*"))
        assert len(backups) == 0, "Backup created for empty entries list"


# ------------------------------------------------------------------
# 4.9 — Lock file detection
# ------------------------------------------------------------------

class TestLockDetection:
    """A lock row in the gnclock table triggers a clear GnuCashError."""

    def test_locked_book_raises_gnucash_error(self, gnucash_book: Path) -> None:
        # Insert a fake lock row into the gnclock table as GnuCash would
        import sqlite3

        conn = sqlite3.connect(str(gnucash_book))
        conn.execute(
            "INSERT INTO gnclock (hostname, pid) VALUES (?, ?)",
            ("fakehost", 99999),
        )
        conn.commit()
        conn.close()

        entry = JournalEntry(
            verification_number="50001",
            entry_date=date(2026, 6, 1),
            description="Should fail due to lock",
            splits=(
                JournalEntrySplit(account_code=1930, amount=Decimal("100.00")),
                JournalEntrySplit(account_code=3010, amount=Decimal("-100.00")),
            ),
        )

        with pytest.raises(GnuCashError, match="locked"):
            write_transactions(gnucash_book, [entry])
