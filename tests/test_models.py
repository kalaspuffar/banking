"""Tests for bookkeeping.models — dataclass behavior, Decimal precision, exceptions."""

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from bookkeeping.models import (
    BankTransaction,
    BookkeepingError,
    CSVParseError,
    CategorizationSuggestion,
    CompanyInfo,
    GnuCashError,
    ImportResult,
    JournalEntry,
    JournalEntrySplit,
    Rule,
    RulesDBError,
    VATSplit,
)


# ---------------------------------------------------------------------------
# BankTransaction validation
# ---------------------------------------------------------------------------

class TestBankTransactionValidation:
    def test_accepts_empty_verification_number(self) -> None:
        """Transactions without a Verifikationsnummer are valid; the dedup
        module treats them as always-new."""
        txn = BankTransaction(
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            verification_number="",
            text="Test",
            amount=Decimal("0"),
            balance=Decimal("0"),
        )
        assert txn.verification_number == ""

    def test_rejects_float_amount(self) -> None:
        with pytest.raises(TypeError, match="amount must be Decimal"):
            BankTransaction(
                booking_date=date(2026, 1, 1),
                value_date=date(2026, 1, 1),
                verification_number="1",
                text="Test",
                amount=100.0,  # type: ignore[arg-type]
                balance=Decimal("0"),
            )

    def test_rejects_float_balance(self) -> None:
        with pytest.raises(TypeError, match="balance must be Decimal"):
            BankTransaction(
                booking_date=date(2026, 1, 1),
                value_date=date(2026, 1, 1),
                verification_number="1",
                text="Test",
                amount=Decimal("0"),
                balance=100.0,  # type: ignore[arg-type]
            )

    def test_accepts_3_decimal_amount(
        self, sample_bank_transaction_3_decimal: BankTransaction
    ) -> None:
        """The bank CSV uses 3-decimal amounts like -100.000."""
        assert sample_bank_transaction_3_decimal.amount == Decimal("-100.000")
        assert isinstance(sample_bank_transaction_3_decimal.amount, Decimal)


# ---------------------------------------------------------------------------
# Frozen dataclass immutability
# ---------------------------------------------------------------------------

class TestBankTransactionImmutability:
    def test_cannot_modify_amount(self, sample_bank_transaction: BankTransaction) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_bank_transaction.amount = Decimal("0")  # type: ignore[misc]

    def test_cannot_modify_text(self, sample_bank_transaction: BankTransaction) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_bank_transaction.text = "changed"  # type: ignore[misc]


class TestVATSplitImmutability:
    def test_cannot_modify_net_amount(self) -> None:
        split = VATSplit(net_amount=Decimal("-100.00"), vat_amount=Decimal("-25.00"))
        with pytest.raises(FrozenInstanceError):
            split.net_amount = Decimal("0")  # type: ignore[misc]


class TestJournalEntryImmutability:
    def test_cannot_modify_entry_date(self, sample_journal_entry: JournalEntry) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_journal_entry.entry_date = date(2025, 1, 1)  # type: ignore[misc]

    def test_splits_is_tuple(self, sample_journal_entry: JournalEntry) -> None:
        assert isinstance(sample_journal_entry.splits, tuple)

    def test_splits_converted_from_list(self) -> None:
        """Lists passed for splits are automatically converted to tuples."""
        entry = JournalEntry(
            verification_number="1",
            entry_date=date(2026, 1, 1),
            description="Test",
            splits=[
                JournalEntrySplit(account_code=1930, amount=Decimal("100")),
                JournalEntrySplit(account_code=3010, amount=Decimal("-100")),
            ],
        )
        assert isinstance(entry.splits, tuple)

    def test_rejects_unbalanced_splits(self) -> None:
        with pytest.raises(ValueError, match="Splits must sum to zero"):
            JournalEntry(
                verification_number="1",
                entry_date=date(2026, 1, 1),
                description="Test",
                splits=[
                    JournalEntrySplit(account_code=1930, amount=Decimal("100")),
                    JournalEntrySplit(account_code=3010, amount=Decimal("-50")),
                ],
            )


class TestCompanyInfoImmutability:
    def test_cannot_modify_name(self) -> None:
        info = CompanyInfo(name="Test AB", org_number="123456-7890", address="Stockholm", fiscal_year=2025)
        with pytest.raises(FrozenInstanceError):
            info.name = "Changed"  # type: ignore[misc]


class TestImportResultImmutability:
    def test_cannot_modify_transactions_written(self) -> None:
        result = ImportResult(transactions_written=5)
        with pytest.raises(FrozenInstanceError):
            result.transactions_written = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Decimal precision
# ---------------------------------------------------------------------------

class TestDecimalPrecision:
    def test_bank_transaction_preserves_decimal(self) -> None:
        tx = BankTransaction(
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            verification_number="1",
            text="Test",
            amount=Decimal("-125.50"),
            balance=Decimal("9874.50"),
        )
        assert tx.amount == Decimal("-125.50")
        assert isinstance(tx.amount, Decimal)

    def test_vat_split_preserves_decimal(self) -> None:
        split = VATSplit(net_amount=Decimal("-100.00"), vat_amount=Decimal("-25.00"))
        assert split.net_amount + split.vat_amount == Decimal("-125.00")

    def test_journal_entry_splits_sum_to_zero(self, sample_journal_entry: JournalEntry) -> None:
        total = sum(s.amount for s in sample_journal_entry.splits)
        assert total == Decimal("0.00")


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_csv_parse_error_is_bookkeeping_error(self) -> None:
        with pytest.raises(BookkeepingError):
            raise CSVParseError("Invalid row at line 5")

    def test_gnucash_error_is_bookkeeping_error(self) -> None:
        with pytest.raises(BookkeepingError):
            raise GnuCashError("Book is locked")

    def test_rules_db_error_is_bookkeeping_error(self) -> None:
        with pytest.raises(BookkeepingError):
            raise RulesDBError("Database corrupted")

    def test_exception_carries_message(self) -> None:
        error = CSVParseError("Invalid row at line 5")
        assert str(error) == "Invalid row at line 5"

    def test_exceptions_are_distinct(self) -> None:
        with pytest.raises(CSVParseError):
            raise CSVParseError("test")
        # GnuCashError should NOT be caught by CSVParseError handler
        with pytest.raises(GnuCashError):
            raise GnuCashError("test")


# ---------------------------------------------------------------------------
# Rule mutability
# ---------------------------------------------------------------------------

class TestRuleMutability:
    def test_can_modify_last_used(self, sample_rule: Rule) -> None:
        new_date = date(2026, 2, 15)
        sample_rule.last_used = new_date
        assert sample_rule.last_used == new_date

    def test_can_modify_use_count(self, sample_rule: Rule) -> None:
        sample_rule.use_count += 1
        assert sample_rule.use_count == 4


# ---------------------------------------------------------------------------
# CategorizationSuggestion
# ---------------------------------------------------------------------------

class TestCategorizationSuggestion:
    def test_references_transaction(self, sample_bank_transaction: BankTransaction) -> None:
        suggestion = CategorizationSuggestion(
            transaction=sample_bank_transaction,
            debit_account=6540,
            credit_account=1930,
            vat_rate=Decimal("0.25"),
            vat_account=2640,
            confidence="exact",
            rule_id=1,
        )
        assert suggestion.transaction is sample_bank_transaction
        assert suggestion.confidence == "exact"


# ---------------------------------------------------------------------------
# ImportResult defaults
# ---------------------------------------------------------------------------

class TestImportResultDefaults:
    def test_default_errors_is_empty_tuple(self) -> None:
        result = ImportResult(transactions_written=3)
        assert result.errors == ()
        assert isinstance(result.errors, tuple)
        assert result.transactions_written == 3

    def test_errors_is_tuple(self) -> None:
        result = ImportResult(transactions_written=0, errors=("bad row",))
        assert isinstance(result.errors, tuple)
        assert result.errors == ("bad row",)


# ---------------------------------------------------------------------------
# Rule and CategorizationSuggestion validation
# ---------------------------------------------------------------------------

class TestRuleValidation:
    def test_rejects_invalid_match_type(self) -> None:
        with pytest.raises(ValueError, match="match_type must be one of"):
            Rule(
                id=None,
                pattern="test",
                match_type="regex",  # type: ignore[arg-type]
                debit_account=1930,
                credit_account=3010,
                vat_rate=Decimal("0.25"),
                vat_account=2610,
                last_used=date(2026, 1, 1),
                use_count=0,
            )

    def test_accepts_exact(self) -> None:
        rule = Rule(
            id=None, pattern="test", match_type="exact",
            debit_account=1930, credit_account=3010,
            vat_rate=Decimal("0"), vat_account=None,
            last_used=date(2026, 1, 1), use_count=0,
        )
        assert rule.match_type == "exact"

    def test_accepts_contains(self) -> None:
        rule = Rule(
            id=None, pattern="test", match_type="contains",
            debit_account=1930, credit_account=3010,
            vat_rate=Decimal("0"), vat_account=None,
            last_used=date(2026, 1, 1), use_count=0,
        )
        assert rule.match_type == "contains"


class TestCategorizationSuggestionValidation:
    def test_rejects_invalid_confidence(self, sample_bank_transaction: BankTransaction) -> None:
        with pytest.raises(ValueError, match="confidence must be one of"):
            CategorizationSuggestion(
                transaction=sample_bank_transaction,
                debit_account=6540,
                credit_account=1930,
                vat_rate=Decimal("0.25"),
                vat_account=2640,
                confidence="high",  # type: ignore[arg-type]
                rule_id=1,
            )
