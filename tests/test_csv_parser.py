"""Tests for the bank CSV parser module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bookkeeping.csv_parser import parse_bank_csv
from bookkeeping.models import BankTransaction, CSVParseError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidCSVParsing:
    """Tests for successful parsing of well-formed CSV files."""

    def test_parse_sample_fixture(self, tmp_path: Path) -> None:
        """The sample fixture file parses into the expected number of transactions."""
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        assert len(result) == 6

    def test_transactions_are_bank_transaction_objects(self) -> None:
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        assert all(isinstance(t, BankTransaction) for t in result)

    def test_sorted_by_booking_date_ascending(self) -> None:
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        dates = [t.booking_date for t in result]
        assert dates == sorted(dates)

    def test_amount_parsed_correctly(self) -> None:
        """Amounts are quantized to 2 decimal places."""
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        # The first row (after sorting by date) is 2026-01-02 with amount 15000.00
        earliest = result[0]
        assert earliest.amount == Decimal("15000.00")

    def test_date_fields_are_date_objects(self) -> None:
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        for txn in result:
            assert isinstance(txn.booking_date, date)
            assert isinstance(txn.value_date, date)

    def test_verification_number_preserved(self) -> None:
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        numbers = {t.verification_number for t in result}
        assert "123990558" in numbers

    def test_text_field_preserved(self) -> None:
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        texts = {t.text for t in result}
        assert "Hyra kontor" in texts


class TestEmptyCSV:
    """Tests for CSV files with only a header row."""

    def test_empty_csv_returns_empty_list(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)
        assert result == []


# ---------------------------------------------------------------------------
# Header validation
# ---------------------------------------------------------------------------

class TestInvalidHeaders:
    """Tests for CSV files with wrong or missing headers."""

    def test_wrong_column_names_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad_headers.csv"
        csv_file.write_text(
            "Date;ValueDate;Ref;Description;Amount;Balance\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Unexpected CSV headers"):
            parse_bank_csv(csv_file)

    def test_missing_column_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "missing_col.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Unexpected CSV headers"):
            parse_bank_csv(csv_file)

    def test_completely_empty_file_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty_file.csv"
        csv_file.write_text("", encoding="utf-8")
        with pytest.raises(CSVParseError, match="empty"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# Date parsing errors
# ---------------------------------------------------------------------------

class TestMalformedDates:
    """Tests for rows with unparseable date values."""

    def test_invalid_date_format_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad_date.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "28/01/2026;2026-01-28;12345;Test;-100.000;1000.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*invalid date.*Bokföringsdatum"):
            parse_bank_csv(csv_file)

    def test_invalid_value_date_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad_value_date.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;not-a-date;12345;Test;-100.000;1000.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*invalid date.*Valutadatum"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# Amount parsing errors
# ---------------------------------------------------------------------------

class TestMalformedAmounts:
    """Tests for rows with unparseable amount values."""

    def test_non_numeric_amount_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad_amount.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;abc;1000.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*invalid amount.*Belopp"):
            parse_bank_csv(csv_file)

    def test_non_numeric_balance_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "bad_balance.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-100.000;xyz\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*invalid amount.*Saldo"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# Missing fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    """Tests for rows with wrong number of columns."""

    def test_too_few_fields_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "short_row.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*expected 6 fields"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# Edge cases (Task 3.2)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests: UTF-8 Swedish characters, negative zero, large amounts."""

    def test_utf8_swedish_characters_in_text(self, tmp_path: Path) -> None:
        """Swedish characters å, ä, ö are preserved in the text field."""
        csv_file = tmp_path / "swedish.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Överföring från sparkonto;-500.000;1000.000\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)
        assert result[0].text == "Överföring från sparkonto"

    def test_negative_zero_amount(self, tmp_path: Path) -> None:
        """Negative zero normalizes to Decimal('0.00') or Decimal('-0.00') — both valid."""
        csv_file = tmp_path / "neg_zero.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-0.000;1000.000\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)
        # -0.00 is a valid Decimal; its absolute value should be zero
        assert abs(result[0].amount) == Decimal("0.00")

    def test_very_large_amount(self, tmp_path: Path) -> None:
        """Parser handles large amounts without overflow."""
        csv_file = tmp_path / "large.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Stor betalning;-9999999.990;50000000.000\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)
        assert result[0].amount == Decimal("-9999999.99")
        assert result[0].balance == Decimal("50000000.00")
