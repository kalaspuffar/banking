"""Shared data models and exception hierarchy for the bokföring package.

All monetary amounts use Decimal for exact arithmetic. Most models are frozen
dataclasses (immutable value objects). Rule is mutable to support in-place
updates from database operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class BokforingError(Exception):
    """Base exception for all bokföring domain errors."""


class CSVParseError(BokforingError):
    """Raised when a bank CSV file cannot be parsed."""


class GnuCashError(BokforingError):
    """Raised when a GnuCash operation fails."""


class RulesDBError(BokforingError):
    """Raised when a rules database operation fails."""


# ---------------------------------------------------------------------------
# Value objects (frozen dataclasses)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BankTransaction:
    """A single transaction parsed from a bank CSV export.

    Attributes:
        bokforingsdatum: Booking date.
        valutadatum: Value (settlement) date.
        verifikationsnummer: Unique transaction ID assigned by the bank.
        text: Human-readable transaction description.
        belopp: Amount in SEK (negative = expense, positive = income).
        saldo: Running account balance after this transaction.
    """

    bokforingsdatum: date
    valutadatum: date
    verifikationsnummer: str
    text: str
    belopp: Decimal
    saldo: Decimal


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
    confidence: str
    rule_id: int | None


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
        verifikationsnummer: Unique transaction ID from the bank.
        datum: Booking date.
        beskrivning: Transaction description.
        splits: List of splits that must sum to zero.
    """

    verifikationsnummer: str
    datum: date
    beskrivning: str
    splits: list[JournalEntrySplit]


@dataclass(frozen=True)
class CompanyInfo:
    """Company/proprietor information for report headers.

    Attributes:
        name: Company or proprietor name.
        org_nummer: Swedish organisationsnummer.
        address: Postal address.
        fiscal_year: The fiscal year (e.g., 2025).
    """

    name: str
    org_nummer: str
    address: str
    fiscal_year: int


@dataclass(frozen=True)
class ImportResult:
    """Outcome of writing transactions to GnuCash.

    Attributes:
        transactions_written: Number of transactions successfully committed.
        errors: List of error descriptions for any failed transactions.
    """

    transactions_written: int
    errors: list[str] = field(default_factory=list)


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
    match_type: str
    debit_account: int
    credit_account: int
    vat_rate: Decimal
    vat_account: int | None
    last_used: date
    use_count: int
