"""Tests for the duplicate detection module.

Each test uses a programmatically created GnuCash SQLite book via piecash,
ensuring repeatable and isolated test conditions.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import piecash
import pytest

from bookkeeping.dedup import filter_duplicates
from bookkeeping.models import BankTransaction, GnuCashError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transaction(
    verification_number: str,
    text: str = "Test transaction",
    amount: Decimal = Decimal("-100.00"),
) -> BankTransaction:
    """Create a BankTransaction with sensible defaults."""
    return BankTransaction(
        booking_date=date(2026, 1, 15),
        value_date=date(2026, 1, 15),
        verification_number=verification_number,
        text=text,
        amount=amount,
        balance=Decimal("10000.00"),
    )


def _create_gnucash_book(
    path: Path,
    existing_nums: list[str] | None = None,
) -> None:
    """Create a minimal GnuCash SQLite book with optional transactions.

    Sets up SEK currency, a bank account (1930), and optionally inserts
    transactions with the given ``num`` values so they appear as
    already-imported entries.
    """
    book = piecash.create_book(
        str(path),
        currency="SEK",
        overwrite=True,
    )
    with book:
        if existing_nums:
            bank_account = piecash.Account(
                name="Företagskonto",
                type="BANK",
                commodity=book.default_currency,
                parent=book.root_account,
                code="1930",
            )
            # Need an equity account for the other side of splits
            equity_account = piecash.Account(
                name="Eget kapital",
                type="EQUITY",
                commodity=book.default_currency,
                parent=book.root_account,
                code="2010",
            )
            book.flush()

            for num in existing_nums:
                piecash.Transaction(
                    currency=book.default_currency,
                    description=f"Existing txn {num}",
                    num=num,
                    post_date=date(2026, 1, 10),
                    splits=[
                        piecash.Split(
                            account=bank_account,
                            value=Decimal("-100.00"),
                        ),
                        piecash.Split(
                            account=equity_account,
                            value=Decimal("100.00"),
                        ),
                    ],
                )

        book.save()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_book(tmp_path: Path) -> Path:
    """A GnuCash book with no transactions."""
    book_path = tmp_path / "empty.gnucash"
    _create_gnucash_book(book_path)
    return book_path


@pytest.fixture
def book_with_transactions(tmp_path: Path) -> Path:
    """A GnuCash book containing transactions with num '1001', '1002', '1003'."""
    book_path = tmp_path / "with_txns.gnucash"
    _create_gnucash_book(book_path, existing_nums=["1001", "1002", "1003"])
    return book_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAllNew:
    """All transactions are new when the book is empty."""

    def test_all_new_against_empty_book(self, empty_book: Path) -> None:
        transactions = [
            _make_transaction("2001"),
            _make_transaction("2002"),
            _make_transaction("2003"),
            _make_transaction("2004"),
            _make_transaction("2005"),
        ]

        new, duplicates = filter_duplicates(transactions, empty_book)

        assert len(new) == 5
        assert len(duplicates) == 0
        assert new == transactions


class TestAllDuplicates:
    """All transactions are duplicates when every num already exists."""

    def test_all_duplicates(self, book_with_transactions: Path) -> None:
        transactions = [
            _make_transaction("1001"),
            _make_transaction("1002"),
            _make_transaction("1003"),
        ]

        new, duplicates = filter_duplicates(transactions, book_with_transactions)

        assert len(new) == 0
        assert len(duplicates) == 3
        assert duplicates == transactions


class TestMixedScenario:
    """Some transactions are new, some are duplicates."""

    def test_mixed_partitioning(self, book_with_transactions: Path) -> None:
        transactions = [
            _make_transaction("1001"),  # duplicate
            _make_transaction("1002"),  # duplicate
            _make_transaction("1003"),  # duplicate
            _make_transaction("2001"),  # new
            _make_transaction("2002"),  # new
        ]

        new, duplicates = filter_duplicates(transactions, book_with_transactions)

        assert [t.verification_number for t in new] == ["2001", "2002"]
        assert [t.verification_number for t in duplicates] == ["1001", "1002", "1003"]


class TestExactStringMatch:
    """Matching is exact: '1001' and '01001' are distinct values."""

    def test_leading_zeros_not_equal(self, book_with_transactions: Path) -> None:
        transactions = [
            _make_transaction("01001"),  # NOT a duplicate of "1001"
            _make_transaction("1001"),   # IS a duplicate
        ]

        new, duplicates = filter_duplicates(transactions, book_with_transactions)

        assert [t.verification_number for t in new] == ["01001"]
        assert [t.verification_number for t in duplicates] == ["1001"]


class TestEmptyVerificationNumber:
    """Transactions without a verification number are always treated as new."""

    def test_empty_string_is_new(self, book_with_transactions: Path) -> None:
        transactions = [
            _make_transaction(""),
            _make_transaction("1001"),  # duplicate
        ]

        new, duplicates = filter_duplicates(transactions, book_with_transactions)

        assert len(new) == 1
        assert new[0].verification_number == ""
        assert len(duplicates) == 1
        assert duplicates[0].verification_number == "1001"

    def test_multiple_empty_all_treated_as_new(self, empty_book: Path) -> None:
        transactions = [
            _make_transaction(""),
            _make_transaction(""),
        ]

        new, duplicates = filter_duplicates(transactions, empty_book)

        assert len(new) == 2
        assert len(duplicates) == 0


class TestOrderPreservation:
    """Both output lists preserve the relative order from the input."""

    def test_order_preserved(self, book_with_transactions: Path) -> None:
        transactions = [
            _make_transaction("2001", text="New first"),
            _make_transaction("1001", text="Dup first"),
            _make_transaction("2002", text="New second"),
            _make_transaction("1002", text="Dup second"),
            _make_transaction("2003", text="New third"),
        ]

        new, duplicates = filter_duplicates(transactions, book_with_transactions)

        assert [t.text for t in new] == ["New first", "New second", "New third"]
        assert [t.text for t in duplicates] == ["Dup first", "Dup second"]


class TestInvalidBookPath:
    """Error handling when the GnuCash book file is invalid or missing."""

    def test_nonexistent_book_raises_gnucash_error(self, tmp_path: Path) -> None:
        transactions = [_make_transaction("1001")]
        with pytest.raises(GnuCashError, match="Failed to open GnuCash book"):
            filter_duplicates(transactions, tmp_path / "nonexistent.gnucash")

    def test_corrupt_file_raises_gnucash_error(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / "corrupt.gnucash"
        corrupt_path.write_text("this is not a sqlite file")
        transactions = [_make_transaction("1001")]
        with pytest.raises(GnuCashError, match="Failed to open GnuCash book"):
            filter_duplicates(transactions, corrupt_path)


class TestLargerDataset:
    """Confidence test with a moderately large number of existing transactions."""

    def test_200_existing_transactions(self, tmp_path: Path) -> None:
        existing_nums = [str(i) for i in range(1, 201)]
        book_path = tmp_path / "large.gnucash"
        _create_gnucash_book(book_path, existing_nums=existing_nums)

        # 50 duplicates + 50 new
        transactions = [
            _make_transaction(str(i)) for i in range(176, 226)
        ]

        new, duplicates = filter_duplicates(transactions, book_path)

        assert len(duplicates) == 25  # 176..200 are duplicates
        assert len(new) == 25         # 201..225 are new
        assert {t.verification_number for t in duplicates} == {
            str(i) for i in range(176, 201)
        }
        assert {t.verification_number for t in new} == {
            str(i) for i in range(201, 226)
        }
