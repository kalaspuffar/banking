"""Duplicate detection for bank transaction imports.

Compares incoming BankTransaction verification numbers against existing
GnuCash transaction `num` fields to prevent double-importing when CSV
exports contain overlapping date ranges.
"""

from __future__ import annotations

from pathlib import Path

import piecash

from bookkeeping.models import BankTransaction, GnuCashError


def filter_duplicates(
    transactions: list[BankTransaction],
    gnucash_book_path: Path,
) -> tuple[list[BankTransaction], list[BankTransaction]]:
    """Separate new transactions from those already present in a GnuCash book.

    Opens the GnuCash book in readonly mode, extracts all non-empty
    transaction ``num`` fields into a set, then partitions the input list
    by checking each transaction's ``verification_number`` against that set.

    Transactions with an empty ``verification_number`` are always classified
    as new, since they cannot be matched against any existing entry.

    Args:
        transactions: Bank transactions to check for duplicates.
        gnucash_book_path: Path to the GnuCash SQLite book file.

    Returns:
        A tuple of (new_transactions, duplicate_transactions), both
        preserving the relative order from the input list.
    """
    existing_nums = _load_existing_nums(gnucash_book_path)

    new_transactions: list[BankTransaction] = []
    duplicate_transactions: list[BankTransaction] = []

    for txn in transactions:
        if not txn.verification_number or txn.verification_number not in existing_nums:
            new_transactions.append(txn)
        else:
            duplicate_transactions.append(txn)

    return new_transactions, duplicate_transactions


def _load_existing_nums(gnucash_book_path: Path) -> set[str]:
    """Read all non-empty transaction ``num`` fields from a GnuCash book.

    Args:
        gnucash_book_path: Path to the GnuCash SQLite book file.

    Returns:
        A set of existing transaction ``num`` strings for O(1) lookup.

    Raises:
        GnuCashError: If the book file cannot be opened (missing, corrupt,
            or not a valid GnuCash SQLite file).
    """
    try:
        with piecash.open_book(str(gnucash_book_path), readonly=True) as book:
            return {
                txn.num
                for txn in book.transactions
                if txn.num
            }
    except Exception as exc:
        raise GnuCashError(
            f"Failed to open GnuCash book at {gnucash_book_path}: {exc}"
        ) from exc
