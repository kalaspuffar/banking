"""Tests for the bank CSV parser module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bookkeeping.csv_parser import parse_bank_csv
from bookkeeping.models import BankTransaction, CSVParseError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidCSVParsing:
    """Tests for successful parsing of well-formed CSV files."""

    def test_parse_sample_fixture(self) -> None:
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


# ---------------------------------------------------------------------------
# Integration test against real account.csv (Issue 2)
# ---------------------------------------------------------------------------

class TestRealAccountCSV:
    """Integration tests that parse the actual account.csv from the repo root."""

    @pytest.fixture()
    def account_csv(self) -> Path:
        path = REPO_ROOT / "account.csv"
        if not path.exists():
            pytest.skip("account.csv not present in repo root")
        return path

    def test_parse_account_csv_row_count(self, account_csv: Path) -> None:
        """The real account.csv parses into the expected number of rows."""
        result = parse_bank_csv(account_csv)
        assert len(result) == 6

    def test_parse_account_csv_spot_check_first_row(self, account_csv: Path) -> None:
        """Spot-check a known transaction from account.csv."""
        result = parse_bank_csv(account_csv)
        # Earliest by booking_date: two rows on 2026-01-02
        earliest_pair = [t for t in result if t.booking_date == date(2026, 1, 2)]
        assert len(earliest_pair) == 2
        amounts = {t.amount for t in earliest_pair}
        assert Decimal("-113.58") in amounts
        assert Decimal("-14.58") in amounts

    def test_parse_account_csv_text_with_date_suffix(
        self, account_csv: Path
    ) -> None:
        """Text fields containing date suffixes (e.g., 'test2/26-01-23') are preserved."""
        result = parse_bank_csv(account_csv)
        texts = {t.text for t in result}
        assert "test2/26-01-23" in texts

    def test_parse_account_csv_non_round_amount(self, account_csv: Path) -> None:
        """Non-round amounts like -37.88 are parsed correctly."""
        result = parse_bank_csv(account_csv)
        amounts = {t.amount for t in result}
        assert Decimal("-37.88") in amounts


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

    def test_sub_ore_amount_raises_error(self, tmp_path: Path) -> None:
        """An amount with a non-zero third decimal (sub-öre) is rejected."""
        csv_file = tmp_path / "sub_ore.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-100.005;1000.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="sub-öre"):
            parse_bank_csv(csv_file)

    def test_sub_ore_balance_raises_error(self, tmp_path: Path) -> None:
        """A balance with a non-zero third decimal (sub-öre) is rejected."""
        csv_file = tmp_path / "sub_ore_bal.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-100.000;1000.005\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="sub-öre"):
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
# Empty required fields (Issue 6)
# ---------------------------------------------------------------------------

class TestEmptyRequiredFields:
    """Tests for rows where required string fields are empty."""

    def test_empty_verification_number_is_allowed(self, tmp_path: Path) -> None:
        """Empty verification numbers are valid — some bank transactions lack one."""
        csv_file = tmp_path / "empty_verif.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;;Test;-100.000;1000.000\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)

        assert len(result) == 1
        assert result[0].verification_number == ""

    def test_empty_text_raises_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty_text.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;;-100.000;1000.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="Line 2.*Text.*empty"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# FileNotFoundError (Issue 5)
# ---------------------------------------------------------------------------

class TestFileNotFound:
    """Tests for missing file handling."""

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_bank_csv(tmp_path / "nonexistent.csv")


# ---------------------------------------------------------------------------
# Blank row handling (Issue 3)
# ---------------------------------------------------------------------------

class TestBlankRowHandling:
    """Tests for blank rows in CSV files."""

    def test_trailing_blank_rows_are_skipped(self, tmp_path: Path) -> None:
        """Blank rows at the end of the file are silently ignored."""
        csv_file = tmp_path / "trailing_blank.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-100.000;1000.000\n"
            "\n"
            "\n",
            encoding="utf-8",
        )
        result = parse_bank_csv(csv_file)
        assert len(result) == 1

    def test_blank_row_in_middle_raises_error(self, tmp_path: Path) -> None:
        """A blank row followed by data rows indicates a corrupt file."""
        csv_file = tmp_path / "mid_blank.csv"
        csv_file.write_text(
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2026-01-28;2026-01-28;12345;Test;-100.000;1000.000\n"
            "\n"
            "2026-01-29;2026-01-29;12346;Test2;-200.000;800.000\n",
            encoding="utf-8",
        )
        with pytest.raises(CSVParseError, match="data row found after blank row"):
            parse_bank_csv(csv_file)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestBOMEncoding:
    """Tests for UTF-8 BOM handling in CSV files."""

    def test_bom_encoded_csv_parses_correctly(self) -> None:
        """A CSV saved with UTF-8 BOM parses identically to one without."""
        result_bom = parse_bank_csv(FIXTURES_DIR / "sample_bank_bom.csv")
        result_plain = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        assert len(result_bom) == len(result_plain)
        for bom_txn, plain_txn in zip(result_bom, result_plain):
            assert bom_txn.booking_date == plain_txn.booking_date
            assert bom_txn.text == plain_txn.text
            assert bom_txn.amount == plain_txn.amount
            assert bom_txn.balance == plain_txn.balance

    def test_non_bom_csv_still_parses(self) -> None:
        """Regression guard: non-BOM UTF-8 CSV continues to parse correctly."""
        result = parse_bank_csv(FIXTURES_DIR / "sample_bank.csv")
        assert len(result) == 6
        assert all(isinstance(t, BankTransaction) for t in result)

    def test_bom_header_validation_passes(self, tmp_path: Path) -> None:
        """BOM-prefixed header validates correctly against expected column names."""
        csv_file = tmp_path / "bom_header.csv"
        csv_file.write_bytes(
            b"\xef\xbb\xbf"
            + "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
              "2026-01-28;2026-01-28;12345;Test;-100.000;1000.000\n".encode("utf-8")
        )
        result = parse_bank_csv(csv_file)
        assert len(result) == 1
        assert result[0].text == "Test"


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
