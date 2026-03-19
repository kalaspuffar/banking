"""Bank CSV export parser for Swedish semicolon-delimited transaction files.

Reads CSV files exported by the bank and converts them into validated
BankTransaction objects. Handles Swedish formatting conventions:
- Semicolon field delimiter
- UTF-8 encoding (Swedish characters å, ä, ö in descriptions)
- Three-decimal amount notation (e.g., "-125.000" → Decimal("-125.00"))
- ISO date format YYYY-MM-DD
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bookkeeping.models import BankTransaction, CSVParseError

# Expected column headers in the bank CSV export (Swedish names).
EXPECTED_HEADERS: tuple[str, ...] = (
    "Bokföringsdatum",
    "Valutadatum",
    "Verifikationsnummer",
    "Text",
    "Belopp",
    "Saldo",
)

_FIELD_COUNT = len(EXPECTED_HEADERS)


def _validate_headers(actual_headers: list[str]) -> None:
    """Raise CSVParseError if the header row does not match the expected columns.

    Args:
        actual_headers: Column names read from the first row of the CSV.

    Raises:
        CSVParseError: When headers don't match expected columns.
    """
    actual = tuple(h.strip() for h in actual_headers)
    if actual != EXPECTED_HEADERS:
        raise CSVParseError(
            f"Unexpected CSV headers. "
            f"Expected: {list(EXPECTED_HEADERS)}, got: {list(actual)}"
        )


def _parse_date(value: str, *, line_number: int, field_name: str) -> date:
    """Parse a YYYY-MM-DD date string into a date object.

    Args:
        value: Date string to parse.
        line_number: CSV line number for error reporting.
        field_name: Column name for error reporting.

    Returns:
        Parsed date object.

    Raises:
        CSVParseError: When the date string is not valid YYYY-MM-DD format.
    """
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError) as exc:
        raise CSVParseError(
            f"Line {line_number}: invalid date in '{field_name}': {value!r}"
        ) from exc


def _parse_amount(value: str, *, line_number: int, field_name: str) -> Decimal:
    """Parse a 3-decimal amount string into a Decimal quantized to 2 places.

    The bank exports amounts with three decimal places (e.g., "-125.000").
    The third decimal is always zero — a Swedish convention. This function
    parses the string directly as a Decimal, validates that no sub-öre
    precision would be lost, and quantizes to two decimal places.

    Args:
        value: Amount string to parse (e.g., "-125.000", "10000.000").
        line_number: CSV line number for error reporting.
        field_name: Column name for error reporting.

    Returns:
        Decimal value quantized to two decimal places.

    Raises:
        CSVParseError: When the amount string cannot be parsed as a Decimal,
            or when quantizing would lose sub-öre precision.
    """
    try:
        raw = Decimal(value.strip())
        quantized = raw.quantize(Decimal("0.01"))
        if raw != quantized:
            raise CSVParseError(
                f"Line {line_number}: amount in '{field_name}' has non-zero "
                f"sub-öre digit: {value!r}"
            )
        return quantized
    except (InvalidOperation, AttributeError) as exc:
        raise CSVParseError(
            f"Line {line_number}: invalid amount in '{field_name}': {value!r}"
        ) from exc


def parse_bank_csv(filepath: Path) -> list[BankTransaction]:
    """Parse a bank CSV export into a sorted list of BankTransaction objects.

    Reads a semicolon-delimited, UTF-8 encoded CSV file with the standard
    Swedish bank export format. Validates the header row and every data row,
    raising CSVParseError with line numbers on any malformed input.

    Args:
        filepath: Path to the bank CSV file.

    Returns:
        List of BankTransaction objects sorted by booking_date ascending.

    Raises:
        CSVParseError: On header mismatch, missing fields, or unparseable values.
        FileNotFoundError: If the filepath does not exist.
    """
    transactions: list[BankTransaction] = []

    with filepath.open(mode="r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";")

        # Validate header row
        try:
            headers = next(reader)
        except StopIteration:
            raise CSVParseError("CSV file is empty (no header row)")

        _validate_headers(headers)

        # Parse data rows (line_number starts at 2 because row 1 is the header)
        blank_row_seen_at: int | None = None
        for line_number, row in enumerate(reader, start=2):
            if not any(field.strip() for field in row):
                if blank_row_seen_at is None:
                    blank_row_seen_at = line_number
                continue

            # A non-blank row after a blank row indicates a corrupt file.
            if blank_row_seen_at is not None:
                raise CSVParseError(
                    f"Line {line_number}: data row found after blank row "
                    f"at line {blank_row_seen_at} — file may be corrupt"
                )

            if len(row) != _FIELD_COUNT:
                raise CSVParseError(
                    f"Line {line_number}: expected {_FIELD_COUNT} fields, "
                    f"got {len(row)}"
                )

            booking_date = _parse_date(
                row[0], line_number=line_number, field_name="Bokföringsdatum"
            )
            value_date = _parse_date(
                row[1], line_number=line_number, field_name="Valutadatum"
            )
            verification_number = row[2].strip()
            if not verification_number:
                raise CSVParseError(
                    f"Line {line_number}: 'Verifikationsnummer' is empty"
                )

            text = row[3].strip()
            if not text:
                raise CSVParseError(
                    f"Line {line_number}: 'Text' is empty"
                )
            amount = _parse_amount(
                row[4], line_number=line_number, field_name="Belopp"
            )
            balance = _parse_amount(
                row[5], line_number=line_number, field_name="Saldo"
            )

            transactions.append(
                BankTransaction(
                    booking_date=booking_date,
                    value_date=value_date,
                    verification_number=verification_number,
                    text=text,
                    amount=amount,
                    balance=balance,
                )
            )

    transactions.sort(key=lambda t: t.booking_date)
    return transactions
