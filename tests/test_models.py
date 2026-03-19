"""Tests for bokforing.models — dataclass behavior, Decimal precision, exceptions."""

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest

from bokforing.models import (
    BankTransaction,
    BokforingError,
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
# Frozen dataclass immutability
# ---------------------------------------------------------------------------

class TestBankTransactionImmutability:
    def test_cannot_modify_belopp(self, sample_bank_transaction: BankTransaction) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_bank_transaction.belopp = Decimal("0")  # type: ignore[misc]

    def test_cannot_modify_text(self, sample_bank_transaction: BankTransaction) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_bank_transaction.text = "changed"  # type: ignore[misc]


class TestVATSplitImmutability:
    def test_cannot_modify_net_amount(self) -> None:
        split = VATSplit(net_amount=Decimal("-100.00"), vat_amount=Decimal("-25.00"))
        with pytest.raises(FrozenInstanceError):
            split.net_amount = Decimal("0")  # type: ignore[misc]


class TestJournalEntryImmutability:
    def test_cannot_modify_datum(self, sample_journal_entry: JournalEntry) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_journal_entry.datum = date(2025, 1, 1)  # type: ignore[misc]


class TestCompanyInfoImmutability:
    def test_cannot_modify_name(self) -> None:
        info = CompanyInfo(name="Test AB", org_nummer="123456-7890", address="Stockholm", fiscal_year=2025)
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
            bokforingsdatum=date(2026, 1, 1),
            valutadatum=date(2026, 1, 1),
            verifikationsnummer="1",
            text="Test",
            belopp=Decimal("-125.50"),
            saldo=Decimal("9874.50"),
        )
        assert tx.belopp == Decimal("-125.50")
        assert isinstance(tx.belopp, Decimal)

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
    def test_csv_parse_error_is_bokforing_error(self) -> None:
        with pytest.raises(BokforingError):
            raise CSVParseError("Invalid row at line 5")

    def test_gnucash_error_is_bokforing_error(self) -> None:
        with pytest.raises(BokforingError):
            raise GnuCashError("Book is locked")

    def test_rules_db_error_is_bokforing_error(self) -> None:
        with pytest.raises(BokforingError):
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
    def test_default_errors_is_empty_list(self) -> None:
        result = ImportResult(transactions_written=3)
        assert result.errors == []
        assert result.transactions_written == 3
