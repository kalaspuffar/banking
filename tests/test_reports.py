"""Tests for the PDF report generation module.

Creates a GnuCash test book with known transactions across multiple BAS
accounts, then verifies that each report type produces correct ruta values,
balanced totals, and valid PDF output.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import piecash
import pytest

from bookkeeping.models import CompanyInfo
from bookkeeping.reports import (
    VALID_REPORT_TYPES,
    generate_report,
    _aggregate_by_account,
    _prepare_grundbok_data,
    _prepare_huvudbok_data,
    _prepare_moms_data,
    _prepare_ne_data,
    _round_ore,
    _sum_by_exact_accounts,
    _sum_by_prefix,
    _sum_by_range,
)

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def company_info() -> CompanyInfo:
    """Standard company info for all report tests."""
    return CompanyInfo(
        name="Test AB",
        org_number="551234-5678",
        address="Testgatan 1, 123 45 Teststaden",
        fiscal_year=2025,
    )


@pytest.fixture
def gnucash_book(tmp_path: Path) -> Path:
    """Create a GnuCash test book with known transactions.

    The book contains the following BAS accounts and transactions for 2025:

    Prior year (2024) transaction to set opening balance:
    - 2024-12-15: Opening equity, 2010 credit 50,000 / 1930 debit 50,000

    Fiscal year 2025 transactions:
    1. Consulting invoice: 1930 debit 10,000 / 3010 credit 8,000 / 2610 credit 2,000
    2. YouTube revenue:    1930 debit 6,000 / 3040 credit 6,000
    3. Software license:   6212 debit 800 / 2640 debit 200 / 1930 credit 1,000
    4. IT service:         6540 debit 1,200 / 2640 debit 300 / 1930 credit 1,500

    Account totals for 2025:
    - 1930: +10,000 +6,000 -1,000 -1,500 = +13,500
    - 3010: -8,000 (credit = revenue)
    - 3040: -6,000 (credit = revenue)
    - 2610: -2,000 (credit = output VAT)
    - 2640: +200 +300 = +500 (debit = input VAT)
    - 6212: +800 (debit = expense)
    - 6540: +1,200 (debit = expense)
    - 2010: -50,000 opening (credit = equity), no FY transactions → closing -50,000

    After FY 2025:
    - 2010 closing includes the opening equity (-50,000) plus net result pushed
      to equity. For this test, no closing entries are made, so 2010 stays at -50,000.
    """
    book_path = tmp_path / "test_book.gnucash"

    book = piecash.create_book(
        sqlite_file=str(book_path),
        currency="SEK",
        overwrite=True,
    )

    sek = book.default_currency

    # Create BAS accounts under a root structure
    root = book.root_account

    assets = piecash.Account(
        name="Tillgångar", type="ASSET", parent=root, commodity=sek, placeholder=True
    )
    bank_account = piecash.Account(
        name="Företagskonto", type="ASSET", parent=assets, commodity=sek, code="1930"
    )

    equity_parent = piecash.Account(
        name="Eget kapital parent", type="EQUITY", parent=root, commodity=sek, placeholder=True
    )
    equity = piecash.Account(
        name="Eget kapital", type="EQUITY", parent=equity_parent, commodity=sek, code="2010"
    )

    liabilities = piecash.Account(
        name="Skulder", type="LIABILITY", parent=root, commodity=sek, placeholder=True
    )
    output_vat = piecash.Account(
        name="Utgående moms 25%", type="LIABILITY", parent=liabilities, commodity=sek, code="2610"
    )
    input_vat = piecash.Account(
        name="Ingående moms", type="ASSET", parent=assets, commodity=sek, code="2640"
    )

    income_parent = piecash.Account(
        name="Intäkter", type="INCOME", parent=root, commodity=sek, placeholder=True
    )
    sales_25 = piecash.Account(
        name="Försäljning tjänster 25%", type="INCOME", parent=income_parent, commodity=sek, code="3010"
    )
    sales_free = piecash.Account(
        name="Försäljning tjänster momsfri", type="INCOME", parent=income_parent, commodity=sek, code="3040"
    )

    expense_parent = piecash.Account(
        name="Kostnader", type="EXPENSE", parent=root, commodity=sek, placeholder=True
    )
    software = piecash.Account(
        name="Programvarulicenser", type="EXPENSE", parent=expense_parent, commodity=sek, code="6212"
    )
    it_services = piecash.Account(
        name="IT-tjänster", type="EXPENSE", parent=expense_parent, commodity=sek, code="6540"
    )

    book.flush()

    # --- Prior year transaction: opening equity ---
    piecash.Transaction(
        currency=sek,
        description="Insättning eget kapital",
        post_date=date(2024, 12, 15),
        num="V0001",
        splits=[
            piecash.Split(account=bank_account, value=Decimal("50000")),
            piecash.Split(account=equity, value=Decimal("-50000")),
        ],
    )

    # --- FY 2025 Transaction 1: Consulting invoice 10,000 SEK (25% moms) ---
    piecash.Transaction(
        currency=sek,
        description="Konsultarvode Kund AB",
        post_date=date(2025, 3, 15),
        num="V1001",
        splits=[
            piecash.Split(account=bank_account, value=Decimal("10000")),
            piecash.Split(account=sales_25, value=Decimal("-8000")),
            piecash.Split(account=output_vat, value=Decimal("-2000")),
        ],
    )

    # --- FY 2025 Transaction 2: YouTube revenue 6,000 SEK (momsfri) ---
    piecash.Transaction(
        currency=sek,
        description="YouTube Adsense",
        post_date=date(2025, 6, 1),
        num="V1002",
        splits=[
            piecash.Split(account=bank_account, value=Decimal("6000")),
            piecash.Split(account=sales_free, value=Decimal("-6000")),
        ],
    )

    # --- FY 2025 Transaction 3: Software license -1,000 SEK (25% moms) ---
    piecash.Transaction(
        currency=sek,
        description="Spotify Premium",
        post_date=date(2025, 7, 20),
        num="V1003",
        splits=[
            piecash.Split(account=software, value=Decimal("800")),
            piecash.Split(account=input_vat, value=Decimal("200")),
            piecash.Split(account=bank_account, value=Decimal("-1000")),
        ],
    )

    # --- FY 2025 Transaction 4: IT service -1,500 SEK (25% moms) ---
    piecash.Transaction(
        currency=sek,
        description="Hosting Hetzner",
        post_date=date(2025, 9, 10),
        num="V1004",
        splits=[
            piecash.Split(account=it_services, value=Decimal("1200")),
            piecash.Split(account=input_vat, value=Decimal("300")),
            piecash.Split(account=bank_account, value=Decimal("-1500")),
        ],
    )

    book.flush()
    book.save()

    return book_path


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestAggregationHelpers:
    """Tests for the account aggregation helper functions."""

    def test_sum_by_prefix(self) -> None:
        totals = {"3010": Decimal("8000"), "3040": Decimal("6000"), "6212": Decimal("800")}
        result = _sum_by_prefix(totals, [30])
        assert result == Decimal("14000")

    def test_sum_by_range(self) -> None:
        totals = {
            "5010": Decimal("100"),
            "6212": Decimal("800"),
            "6540": Decimal("1200"),
            "7910": Decimal("500"),
        }
        result = _sum_by_range(totals, [(5000, 6999)])
        assert result == Decimal("2100")

    def test_sum_by_exact_accounts(self) -> None:
        totals = {"2610": Decimal("-2000"), "2640": Decimal("500")}
        result = _sum_by_exact_accounts(totals, [2610])
        assert result == Decimal("-2000")

    def test_round_ore(self) -> None:
        assert _round_ore(Decimal("100.005")) == Decimal("100.00")  # banker's rounding
        assert _round_ore(Decimal("100.015")) == Decimal("100.02")  # banker's rounding
        assert _round_ore(Decimal("100.125")) == Decimal("100.12")


# ---------------------------------------------------------------------------
# Momsdeklaration tests (Task 7.2)
# ---------------------------------------------------------------------------


class TestMomsdeklaration:
    """Verify momsdeklaration ruta values match expected totals."""

    def test_ruta_05_taxable_sales_25(self, gnucash_book: Path) -> None:
        """Ruta 05: account 3010 has -8000 credit → shows 8000 positive."""
        data = _prepare_moms_data(gnucash_book, 2025)
        assert data["rutor"]["05"] == Decimal("8000.00")

    def test_ruta_08_vat_free_sales(self, gnucash_book: Path) -> None:
        """Ruta 08: account 3040 has -6000 credit → shows 6000 positive."""
        data = _prepare_moms_data(gnucash_book, 2025)
        assert data["rutor"]["08"] == Decimal("6000.00")

    def test_ruta_10_output_vat_25(self, gnucash_book: Path) -> None:
        """Ruta 10: account 2610 has -2000 credit → shows 2000 positive."""
        data = _prepare_moms_data(gnucash_book, 2025)
        assert data["rutor"]["10"] == Decimal("2000.00")

    def test_ruta_48_input_vat(self, gnucash_book: Path) -> None:
        """Ruta 48: account 2640 has 200+300=500 debit → shows 500 positive."""
        data = _prepare_moms_data(gnucash_book, 2025)
        assert data["rutor"]["48"] == Decimal("500.00")

    def test_ruta_49_vat_to_pay(self, gnucash_book: Path) -> None:
        """Ruta 49: output VAT (2000) minus input VAT (500) = 1500."""
        data = _prepare_moms_data(gnucash_book, 2025)
        assert data["rutor"]["49"] == Decimal("1500.00")

    def test_ruta_rows_complete(self, gnucash_book: Path) -> None:
        """All expected rutor are present in the ruta_rows list."""
        data = _prepare_moms_data(gnucash_book, 2025)
        ruta_nums = [r["ruta"] for r in data["ruta_rows"]]
        assert ruta_nums == ["05", "06", "07", "08", "10", "11", "12", "48", "49"]


# ---------------------------------------------------------------------------
# NE-bilaga tests (Task 7.3)
# ---------------------------------------------------------------------------


class TestNEBilaga:
    """Verify NE-bilaga ruta values match expected totals."""

    def test_r1_net_revenue(self, gnucash_book: Path) -> None:
        """R1: 30xx accounts total -8000-6000=-14000 → negate → 14000."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["R1"] == Decimal("14000.00")

    def test_r2_other_income(self, gnucash_book: Path) -> None:
        """R2: no 37xx-39xx accounts → 0."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["R2"] == ZERO

    def test_r5_external_costs(self, gnucash_book: Path) -> None:
        """R5: 50xx-69xx accounts: 6212=800 + 6540=1200 = 2000."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["R5"] == Decimal("2000.00")

    def test_r6_other_costs(self, gnucash_book: Path) -> None:
        """R6: no 79xx accounts → 0."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["R6"] == ZERO

    def test_r7_book_result(self, gnucash_book: Path) -> None:
        """R7: R1+R2-R5-R6 = 14000+0-2000-0 = 12000."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["R7"] == Decimal("12000.00")

    def test_b1_opening_equity(self, gnucash_book: Path) -> None:
        """B1: account 2010 balance before 2025 = -50000 → negate → 50000."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["B1"] == Decimal("50000.00")

    def test_b4_closing_equity(self, gnucash_book: Path) -> None:
        """B4: account 2010 balance through 2025 = -50000 (no FY entries) → negate → 50000."""
        data = _prepare_ne_data(gnucash_book, 2025)
        assert data["rutor"]["B4"] == Decimal("50000.00")


# ---------------------------------------------------------------------------
# Grundbok tests (Task 7.4)
# ---------------------------------------------------------------------------


class TestGrundbok:
    """Verify grundbok grand totals and structure."""

    def test_grand_totals_balanced(self, gnucash_book: Path) -> None:
        """Total debet must equal total kredit (double-entry balanced)."""
        data = _prepare_grundbok_data(gnucash_book, 2025)
        assert data["grand_total_debet"] == data["grand_total_kredit"]

    def test_rows_sorted_by_date(self, gnucash_book: Path) -> None:
        """Rows are sorted chronologically by date."""
        data = _prepare_grundbok_data(gnucash_book, 2025)
        dates = [r["datum"] for r in data["rows"]]
        assert dates == sorted(dates)

    def test_all_fiscal_year_transactions_present(self, gnucash_book: Path) -> None:
        """All 4 FY 2025 transactions are present (with multiple splits each)."""
        data = _prepare_grundbok_data(gnucash_book, 2025)
        verifikations = {r["verifikation"] for r in data["rows"]}
        assert verifikations == {"V1001", "V1002", "V1003", "V1004"}

    def test_prior_year_excluded(self, gnucash_book: Path) -> None:
        """The 2024 opening equity transaction is not in the 2025 grundbok."""
        data = _prepare_grundbok_data(gnucash_book, 2025)
        verifikations = {r["verifikation"] for r in data["rows"]}
        assert "V0001" not in verifikations

    def test_grand_totals_correct(self, gnucash_book: Path) -> None:
        """Grand totals match the sum of all debet/kredit in the rows."""
        data = _prepare_grundbok_data(gnucash_book, 2025)
        expected_debet = sum((r["debet"] for r in data["rows"]), ZERO)
        expected_kredit = sum((r["kredit"] for r in data["rows"]), ZERO)
        assert data["grand_total_debet"] == expected_debet
        assert data["grand_total_kredit"] == expected_kredit


# ---------------------------------------------------------------------------
# Huvudbok tests (Task 7.5)
# ---------------------------------------------------------------------------


class TestHuvudbok:
    """Verify huvudbok account balances and structure."""

    def test_accounts_sorted_by_code(self, gnucash_book: Path) -> None:
        """Account sections are sorted by account number ascending."""
        data = _prepare_huvudbok_data(gnucash_book, 2025)
        codes = [a["code"] for a in data["accounts"]]
        assert codes == sorted(codes)

    def test_opening_plus_activity_equals_closing(self, gnucash_book: Path) -> None:
        """For each account: opening + debet - kredit = closing."""
        data = _prepare_huvudbok_data(gnucash_book, 2025)
        for account in data["accounts"]:
            expected_closing = (
                account["opening_balance"]
                + account["subtotal_debet"]
                - account["subtotal_kredit"]
            )
            assert account["closing_balance"] == expected_closing, (
                f"Account {account['code']}: "
                f"opening={account['opening_balance']} + "
                f"debet={account['subtotal_debet']} - "
                f"kredit={account['subtotal_kredit']} != "
                f"closing={account['closing_balance']}"
            )

    def test_bank_account_opening_balance(self, gnucash_book: Path) -> None:
        """Account 1930 has opening balance of 50,000 from prior year."""
        data = _prepare_huvudbok_data(gnucash_book, 2025)
        bank = next(a for a in data["accounts"] if a["code"] == "1930")
        assert bank["opening_balance"] == Decimal("50000.00")

    def test_all_active_accounts_present(self, gnucash_book: Path) -> None:
        """All accounts with FY 2025 activity are represented."""
        data = _prepare_huvudbok_data(gnucash_book, 2025)
        codes = {a["code"] for a in data["accounts"]}
        expected = {"1930", "2610", "2640", "3010", "3040", "6212", "6540"}
        assert codes == expected

    def test_account_transactions_sorted(self, gnucash_book: Path) -> None:
        """Transactions within each account are sorted by date."""
        data = _prepare_huvudbok_data(gnucash_book, 2025)
        for account in data["accounts"]:
            dates = [t["datum"] for t in account["transactions"]]
            assert dates == sorted(dates), f"Account {account['code']} not sorted"


# ---------------------------------------------------------------------------
# PDF generation tests (Task 7.6)
# ---------------------------------------------------------------------------


class TestPDFGeneration:
    """Verify that each report type produces a non-empty PDF file."""

    @pytest.mark.parametrize("report_type", VALID_REPORT_TYPES)
    def test_generates_pdf(
        self,
        report_type: str,
        gnucash_book: Path,
        company_info: CompanyInfo,
        tmp_path: Path,
    ) -> None:
        """Each report type produces a non-empty PDF at the expected path."""
        output_path = tmp_path / f"{report_type}_2025.pdf"
        result = generate_report(
            report_type=report_type,
            gnucash_book_path=gnucash_book,
            fiscal_year=2025,
            output_path=output_path,
            company_info=company_info,
        )
        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_pdf_starts_with_pdf_header(
        self,
        gnucash_book: Path,
        company_info: CompanyInfo,
        tmp_path: Path,
    ) -> None:
        """Generated file is a valid PDF (starts with %PDF magic bytes)."""
        output_path = tmp_path / "moms_2025.pdf"
        generate_report("moms", gnucash_book, 2025, output_path, company_info)
        with open(output_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_invalid_report_type_raises(
        self,
        gnucash_book: Path,
        company_info: CompanyInfo,
        tmp_path: Path,
    ) -> None:
        """An unrecognized report_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid report_type"):
            generate_report(
                "invalid",
                gnucash_book,
                2025,
                tmp_path / "invalid.pdf",
                company_info,
            )

    def test_output_directory_created(
        self,
        gnucash_book: Path,
        company_info: CompanyInfo,
        tmp_path: Path,
    ) -> None:
        """Output directory is created automatically if it doesn't exist."""
        output_path = tmp_path / "subdir" / "deep" / "report.pdf"
        generate_report("moms", gnucash_book, 2025, output_path, company_info)
        assert output_path.exists()
