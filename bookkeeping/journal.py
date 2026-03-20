"""Journal entry construction from categorized transaction data.

Pure-logic module with no GUI or database dependencies. Provides the
``build_journal_entry`` function used by both the CLI-only import path
and the GTK4 verification GUI.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bookkeeping.models import JournalEntry, JournalEntrySplit
from bookkeeping.vat import apply_vat_split


def build_journal_entry(
    verification_number: str,
    booking_date: date,
    description: str,
    amount: Decimal,
    debit_account: int,
    credit_account: int,
    vat_rate: Decimal,
    vat_account: int | None,
) -> JournalEntry:
    """Build a balanced JournalEntry from categorized transaction data.

    Constructs the double-entry splits including VAT splits when the VAT
    rate is non-zero.

    Args:
        verification_number: The bank's unique transaction ID.
        booking_date: Transaction booking date.
        description: Transaction description text.
        amount: Gross transaction amount (negative=expense, positive=income).
        debit_account: BAS account to debit.
        credit_account: BAS account to credit (typically 1930).
        vat_rate: VAT rate as decimal fraction.
        vat_account: VAT account number, or None for 0% VAT.

    Returns:
        A balanced JournalEntry ready for writing to GnuCash.
    """
    splits: list[JournalEntrySplit] = []

    if vat_rate > Decimal("0.00"):
        vat_split = apply_vat_split(amount, vat_rate)
        # Bank split (credit_account, typically 1930)
        splits.append(JournalEntrySplit(
            account_code=credit_account,
            amount=amount,
        ))
        # Expense/revenue split (debit_account)
        splits.append(JournalEntrySplit(
            account_code=debit_account,
            amount=-vat_split.net_amount,
        ))
        # VAT split
        if vat_account is not None:
            splits.append(JournalEntrySplit(
                account_code=vat_account,
                amount=-vat_split.vat_amount,
            ))
    else:
        # No VAT: simple two-way split
        splits.append(JournalEntrySplit(
            account_code=credit_account,
            amount=amount,
        ))
        splits.append(JournalEntrySplit(
            account_code=debit_account,
            amount=-amount,
        ))

    return JournalEntry(
        verification_number=verification_number,
        entry_date=booking_date,
        description=description,
        splits=splits,
    )
