"""GnuCash writer — write balanced double-entry transactions via piecash.

This module bridges the internal JournalEntry model and GnuCash's SQLite
book.  It backs up the book file before every write, looks up BAS accounts
by their ``code`` field, and commits all transactions atomically.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import piecash

from bookkeeping.models import GnuCashError, ImportResult, JournalEntry


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _backup_book(gnucash_book_path: Path) -> Path:
    """Create a timestamped backup of the GnuCash book file.

    The backup is named ``{path}.backup.{YYYYMMDD-HHMMSS}`` and is an exact
    copy (including metadata) produced by :func:`shutil.copy2`.

    Args:
        gnucash_book_path: Path to the GnuCash SQLite file.

    Returns:
        Path to the newly created backup file.

    Raises:
        GnuCashError: If the source file does not exist or the copy fails.
    """
    if not gnucash_book_path.exists():
        raise GnuCashError(
            f"GnuCash book not found: {gnucash_book_path}"
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = gnucash_book_path.with_name(
        f"{gnucash_book_path.name}.backup.{timestamp}"
    )

    try:
        shutil.copy2(gnucash_book_path, backup_path)
    except OSError as exc:
        raise GnuCashError(f"Failed to create backup: {exc}") from exc

    return backup_path


def _lookup_account(
    book: piecash.Book,
    account_code: int,
) -> piecash.Account:
    """Find a GnuCash account by its BAS code.

    Args:
        book: An open piecash Book.
        account_code: BAS 2023 account number (e.g., 1930).

    Returns:
        The matching :class:`piecash.Account`.

    Raises:
        GnuCashError: If no account with the given code exists in the book.
    """
    code_str = str(account_code)
    for account in book.accounts:
        if account.code == code_str:
            return account

    raise GnuCashError(
        f"Account code {account_code} not found in the GnuCash book. "
        f"Ensure the BAS account is set up in your chart of accounts."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_transactions(
    gnucash_book_path: Path,
    entries: list[JournalEntry],
) -> ImportResult:
    """Write journal entries to the GnuCash book.

    Opens the book with piecash, creates Transaction/Split objects, and
    commits atomically (all-or-nothing).  A timestamped backup is created
    before any write.

    Args:
        gnucash_book_path: Path to the GnuCash SQLite file.
        entries: Journal entries to write.  Each entry's splits must
            already sum to zero.

    Returns:
        :class:`ImportResult` with the count of transactions written.

    Raises:
        GnuCashError: If the book file does not exist, is locked, or a
            required account code is not found.
    """
    if not gnucash_book_path.exists():
        raise GnuCashError(
            f"GnuCash book not found: {gnucash_book_path}"
        )

    _backup_book(gnucash_book_path)

    try:
        with piecash.open_book(
            str(gnucash_book_path),
            readonly=False,
            open_if_lock=False,
        ) as book:
            currency = book.default_currency

            # Resolve all account codes before creating any transactions
            # (fail fast if any code is missing).
            account_cache: dict[int, piecash.Account] = {}
            for entry in entries:
                for split in entry.splits:
                    if split.account_code not in account_cache:
                        account_cache[split.account_code] = _lookup_account(
                            book, split.account_code
                        )

            # Create transactions
            for entry in entries:
                txn = piecash.Transaction(
                    currency=currency,
                    description=entry.description,
                    post_date=entry.entry_date,
                    num=entry.verification_number,
                    splits=[
                        piecash.Split(
                            account=account_cache[s.account_code],
                            value=s.amount,
                        )
                        for s in entry.splits
                    ],
                )

            book.save()

    except GnuCashError:
        raise
    except Exception as exc:
        # Catch piecash / SQLAlchemy lock errors and wrap them
        exc_msg = str(exc).lower()
        if "lock" in exc_msg or "locked" in exc_msg:
            raise GnuCashError(
                "The GnuCash book is locked — is it open in GnuCash? "
                "Close GnuCash and try again."
            ) from exc
        raise GnuCashError(
            f"Failed to write transactions to GnuCash: {exc}"
        ) from exc

    return ImportResult(transactions_written=len(entries))
