"""Shared data models and exception hierarchy for the bookkeeping package.

All monetary amounts use Decimal for exact arithmetic. Most models are frozen
dataclasses (immutable value objects). Rule is mutable to support in-place
updates from database operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

# Constrained string types per specification
MatchType = Literal["exact", "contains"]
Confidence = Literal["exact", "pattern", "none"]

_VALID_MATCH_TYPES: frozenset[str] = frozenset({"exact", "contains"})
_VALID_CONFIDENCES: frozenset[str] = frozenset({"exact", "pattern", "none"})


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class BookkeepingError(Exception):
    """Base exception for all bookkeeping domain errors."""


class CSVParseError(BookkeepingError):
    """Raised when a bank CSV file cannot be parsed."""


class GnuCashError(BookkeepingError):
    """Raised when a GnuCash operation fails."""


class RulesDBError(BookkeepingError):
    """Raised when a rules database operation fails."""


# ---------------------------------------------------------------------------
# Value objects (frozen dataclasses)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BankTransaction:
    """A single transaction parsed from a bank CSV export.

    The bank CSV column names are Swedish (Bokföringsdatum, Belopp, etc.)
    but fields use English names for code clarity.

    Attributes:
        booking_date: Booking date (CSV: Bokföringsdatum).
        value_date: Value/settlement date (CSV: Valutadatum).
        verification_number: Unique transaction ID from the bank (CSV: Verifikationsnummer).
        text: Human-readable transaction description (CSV: Text).
        amount: Amount in SEK, negative = expense, positive = income (CSV: Belopp).
        balance: Running account balance after this transaction (CSV: Saldo).
    """

    booking_date: date
    value_date: date
    verification_number: str
    text: str
    amount: Decimal
    balance: Decimal

    def __post_init__(self) -> None:
        if not self.verification_number:
            raise ValueError("verification_number must be non-empty")
        if not isinstance(self.amount, Decimal):
            raise TypeError(f"amount must be Decimal, got {type(self.amount).__name__}")
        if not isinstance(self.balance, Decimal):
            raise TypeError(f"balance must be Decimal, got {type(self.balance).__name__}")


@dataclass(frozen=True)
class VATSplit:
    """Result of splitting a gross amount into net and VAT components.

    Attributes:
        net_amount: Amount excluding VAT.
        vat_amount: The VAT portion.
    """

    net_amount: Decimal
    vat_amount: Decimal


@dataclass(frozen=True)
class CategorizationSuggestion:
    """A suggested BAS 2023 account mapping for a bank transaction.

    Attributes:
        transaction: The originating bank transaction.
        debit_account: BAS account number to debit (e.g., 1930).
        credit_account: BAS account number to credit (e.g., 3010).
        vat_rate: VAT rate as a decimal (0.00, 0.06, 0.12, or 0.25).
        vat_account: BAS VAT account number, or None if VAT rate is 0%.
        confidence: Match quality — "exact", "pattern", or "none".
        rule_id: ID of the matching rule in the rules database, or None.
    """

    transaction: BankTransaction
    debit_account: int
    credit_account: int
    vat_rate: Decimal
    vat_account: int | None
    confidence: Confidence
    rule_id: int | None

    def __post_init__(self) -> None:
        if self.confidence not in _VALID_CONFIDENCES:
            raise ValueError(
                f"confidence must be one of {sorted(_VALID_CONFIDENCES)}, "
                f"got {self.confidence!r}"
            )


@dataclass(frozen=True)
class JournalEntrySplit:
    """A single split (leg) of a double-entry journal entry.

    Attributes:
        account_code: BAS account number.
        amount: Positive means debit, negative means credit.
    """

    account_code: int
    amount: Decimal


@dataclass(frozen=True)
class JournalEntry:
    """A complete double-entry journal entry ready to write to GnuCash.

    The sum of all split amounts must equal zero for the entry to be balanced.

    Attributes:
        verification_number: Unique transaction ID from the bank.
        entry_date: Booking date.
        description: Transaction description.
        splits: Immutable tuple of splits that must sum to zero.
    """

    verification_number: str
    entry_date: date
    description: str
    splits: tuple[JournalEntrySplit, ...]

    def __post_init__(self) -> None:
        # Convert list input to tuple for true immutability
        if isinstance(self.splits, list):
            object.__setattr__(self, "splits", tuple(self.splits))
        total = sum(s.amount for s in self.splits)
        if total != Decimal("0"):
            raise ValueError(f"Splits must sum to zero, got {total}")


@dataclass(frozen=True)
class CompanyInfo:
    """Company/proprietor information for report headers.

    Attributes:
        name: Company or proprietor name.
        org_number: Swedish organisationsnummer.
        address: Postal address.
        fiscal_year: The fiscal year (e.g., 2025).
    """

    name: str
    org_number: str
    address: str
    fiscal_year: int


@dataclass(frozen=True)
class ImportResult:
    """Outcome of writing transactions to GnuCash.

    Attributes:
        transactions_written: Number of transactions successfully committed.
        errors: Immutable tuple of error descriptions for any failed transactions.
    """

    transactions_written: int
    errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Mutable model (database entity)
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    """A categorization rule stored in the rules database.

    Mutable because fields like last_used and use_count are updated in place
    during database operations.

    Attributes:
        id: Database primary key, or None for unsaved rules.
        pattern: Text pattern to match against transaction descriptions.
        match_type: Either "exact" or "contains".
        debit_account: BAS account number to debit.
        credit_account: BAS account number to credit.
        vat_rate: VAT rate as a decimal.
        vat_account: BAS VAT account number, or None if 0% VAT.
        last_used: Date when this rule was last applied.
        use_count: Number of times this rule has been applied.
    """

    id: int | None
    pattern: str
    match_type: MatchType
    debit_account: int
    credit_account: int
    vat_rate: Decimal
    vat_account: int | None
    last_used: date
    use_count: int

    def __post_init__(self) -> None:
        if self.match_type not in _VALID_MATCH_TYPES:
            raise ValueError(
                f"match_type must be one of {sorted(_VALID_MATCH_TYPES)}, "
                f"got {self.match_type!r}"
            )
