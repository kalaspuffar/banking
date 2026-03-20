"""PDF report generation for Swedish bookkeeping.

Generates four report types from GnuCash data:
- Momsdeklaration (VAT return, SKV 4700)
- NE-bilaga (income tax attachment, INK1)
- Grundbok (chronological journal)
- Huvudbok (general ledger by account)

Each report queries the GnuCash book via piecash, aggregates amounts by BAS
account ranges, renders an HTML template with Jinja2, and converts to A4 PDF
via WeasyPrint.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

import jinja2
import piecash
import weasyprint

from bookkeeping.models import CompanyInfo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_REPORT_TYPES = ("moms", "ne", "grundbok", "huvudbok")

ZERO = Decimal("0.00")

# SKV 4700 ruta mapping: ruta number → list of account codes
# Each entry maps a ruta to the accounts whose totals feed it.
MOMS_RUTA_ACCOUNTS: dict[str, list[int]] = {
    "05": [3010],       # Momspliktig försäljning 25%
    "06": [3011],       # Momspliktig försäljning 12%
    "07": [3012],       # Momspliktig försäljning 6%
    "08": [3040],       # Momsfri försäljning
    "10": [2610],       # Utgående moms 25%
    "11": [2620],       # Utgående moms 12%
    "12": [2630],       # Utgående moms 6%
    "48": [2640],       # Ingående moms
}

MOMS_RUTA_DESCRIPTIONS: dict[str, str] = {
    "05": "Momspliktig försäljning exkl. moms (25%)",
    "06": "Momspliktig försäljning exkl. moms (12%)",
    "07": "Momspliktig försäljning exkl. moms (6%)",
    "08": "Momsfri försäljning",
    "10": "Utgående moms 25%",
    "11": "Utgående moms 12%",
    "12": "Utgående moms 6%",
    "48": "Ingående moms att dra av",
    "49": "Moms att betala eller få tillbaka",
}

# INK1 NE-bilaga ruta mapping: ruta → (type, account ranges)
# type is "prefix" for account prefix match, "range" for range match,
# "exact" for single account, or "computed" for derived values.
NE_RUTA_CONFIG: dict[str, dict[str, Any]] = {
    "R1": {"type": "prefix", "prefixes": [30], "description": "Nettoomsättning"},
    "R2": {
        "type": "range",
        "ranges": [(3700, 3999)],
        "description": "Övriga rörelseintäkter",
    },
    "R5": {
        "type": "range",
        "ranges": [(5000, 6999)],
        "description": "Övriga externa kostnader",
    },
    "R6": {"type": "prefix", "prefixes": [79], "description": "Övriga rörelsekostnader"},
    "R7": {"type": "computed", "description": "Bokfört resultat (R1+R2−R5−R6)"},
    "B1": {
        "type": "opening_balance",
        "account": 2010,
        "description": "Eget kapital vid årets början",
    },
    "B4": {
        "type": "closing_balance",
        "account": 2010,
        "description": "Eget kapital vid årets slut",
    },
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_report(
    report_type: str,
    gnucash_book_path: Path,
    fiscal_year: int,
    output_path: Path,
    company_info: CompanyInfo,
) -> Path:
    """Generate a PDF report for the given fiscal year.

    Args:
        report_type: One of "moms", "ne", "grundbok", "huvudbok".
        gnucash_book_path: Path to the GnuCash SQLite book file.
        fiscal_year: The fiscal year to report on (e.g., 2025).
        output_path: Where to write the generated PDF.
        company_info: Company metadata for report headers.

    Returns:
        Path to the generated PDF file.

    Raises:
        ValueError: If report_type is not one of the valid types.
    """
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(
            f"Invalid report_type {report_type!r}. "
            f"Valid types: {', '.join(VALID_REPORT_TYPES)}"
        )

    dispatcher = {
        "moms": _prepare_moms_data,
        "ne": _prepare_ne_data,
        "grundbok": _prepare_grundbok_data,
        "huvudbok": _prepare_huvudbok_data,
    }

    template_names = {
        "moms": "momsdeklaration.html",
        "ne": "ne_bilaga.html",
        "grundbok": "grundbok.html",
        "huvudbok": "huvudbok.html",
    }

    prepare_fn = dispatcher[report_type]
    report_data = prepare_fn(gnucash_book_path, fiscal_year)

    template_name = template_names[report_type]
    html_content = _render_template(template_name, report_data, company_info)
    _html_to_pdf(html_content, output_path)

    return output_path


# ---------------------------------------------------------------------------
# GnuCash data querying
# ---------------------------------------------------------------------------


def _get_fiscal_year_dates(fiscal_year: int) -> tuple[date, date]:
    """Return the start and end dates for a fiscal year."""
    return date(fiscal_year, 1, 1), date(fiscal_year, 12, 31)


def _query_splits_for_fiscal_year(
    book: piecash.Book, fiscal_year: int
) -> list[piecash.Split]:
    """Fetch all splits for transactions within the fiscal year date range.

    Args:
        book: An open piecash Book instance.
        fiscal_year: The year to query.

    Returns:
        List of piecash Split objects whose parent transaction falls within
        the fiscal year.
    """
    start_date, end_date = _get_fiscal_year_dates(fiscal_year)
    splits = []
    for transaction in book.transactions:
        post_date = transaction.post_date
        if isinstance(post_date, date) and start_date <= post_date <= end_date:
            splits.extend(transaction.splits)
    return splits


def _aggregate_by_account(
    splits: list[piecash.Split],
) -> dict[str, Decimal]:
    """Sum split amounts grouped by account code.

    Args:
        splits: List of piecash Split objects.

    Returns:
        Dictionary mapping account code (str) to total Decimal amount.
    """
    totals: dict[str, Decimal] = {}
    for split in splits:
        code = split.account.code
        if not code:
            continue
        amount = Decimal(str(split.value))
        totals[code] = totals.get(code, ZERO) + amount
    return totals


def _sum_by_prefix(
    account_totals: dict[str, Decimal], prefixes: list[int]
) -> Decimal:
    """Sum account totals for accounts matching any of the given prefixes.

    Args:
        account_totals: Account code → total amount mapping.
        prefixes: Two-digit prefixes to match (e.g., 30 matches 3010, 3040).

    Returns:
        Summed Decimal amount.
    """
    total = ZERO
    prefix_strs = [str(p) for p in prefixes]
    for code, amount in account_totals.items():
        if any(code.startswith(ps) for ps in prefix_strs):
            total += amount
    return total


def _sum_by_range(
    account_totals: dict[str, Decimal],
    ranges: list[tuple[int, int]],
) -> Decimal:
    """Sum account totals for accounts within the given numeric ranges.

    Args:
        account_totals: Account code → total amount mapping.
        ranges: List of (start, end) inclusive ranges for account codes.

    Returns:
        Summed Decimal amount.
    """
    total = ZERO
    for code, amount in account_totals.items():
        try:
            code_int = int(code)
        except ValueError:
            continue
        for range_start, range_end in ranges:
            if range_start <= code_int <= range_end:
                total += amount
                break
    return total


def _sum_by_exact_accounts(
    account_totals: dict[str, Decimal], accounts: list[int]
) -> Decimal:
    """Sum account totals for specific account codes.

    Args:
        account_totals: Account code → total amount mapping.
        accounts: Exact account codes to sum.

    Returns:
        Summed Decimal amount.
    """
    total = ZERO
    for acct in accounts:
        total += account_totals.get(str(acct), ZERO)
    return total


def _round_ore(amount: Decimal) -> Decimal:
    """Round to öre (2 decimal places) using banker's rounding."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


# ---------------------------------------------------------------------------
# Momsdeklaration data preparation
# ---------------------------------------------------------------------------


def _prepare_moms_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return momsdeklaration ruta→amount mapping.

    Revenue accounts (30xx) store credits as negative in GnuCash, so
    we negate them to display as positive amounts on the form. VAT output
    accounts (26xx) are also credit accounts (negative). Input VAT (2640)
    is a debit account (positive).
    """
    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        splits = _query_splits_for_fiscal_year(book, fiscal_year)
        account_totals = _aggregate_by_account(splits)

    rutor: dict[str, Decimal] = {}
    for ruta, accounts in MOMS_RUTA_ACCOUNTS.items():
        raw = _sum_by_exact_accounts(account_totals, accounts)
        # Revenue and output VAT accounts are credit accounts in GnuCash
        # (stored as negative). Negate to show positive on the form.
        # Input VAT (ruta 48, account 2640) is a debit account (positive).
        if ruta in ("05", "06", "07", "08", "10", "11", "12"):
            rutor[ruta] = _round_ore(-raw)
        else:
            rutor[ruta] = _round_ore(raw)

    # Ruta 49: output VAT minus input VAT
    output_vat = (
        rutor.get("10", ZERO) + rutor.get("11", ZERO) + rutor.get("12", ZERO)
    )
    input_vat = rutor.get("48", ZERO)
    rutor["49"] = _round_ore(output_vat - input_vat)

    ruta_rows = []
    for ruta_num in ["05", "06", "07", "08", "10", "11", "12", "48", "49"]:
        amount = rutor.get(ruta_num, ZERO)
        ruta_rows.append({
            "ruta": ruta_num,
            "description": MOMS_RUTA_DESCRIPTIONS[ruta_num],
            "amount": amount,
        })

    return {
        "report_title": "Momsdeklaration",
        "reference": "SKV 4700",
        "fiscal_year": fiscal_year,
        "ruta_rows": ruta_rows,
        "rutor": rutor,
    }


# ---------------------------------------------------------------------------
# NE-bilaga data preparation
# ---------------------------------------------------------------------------


def _compute_account_balance_at_date(
    book: piecash.Book,
    account_code: int,
    target_date: date,
) -> Decimal:
    """Compute the balance of an account up to (and including) a target date.

    Sums all split amounts for the account where the parent transaction's
    post_date is on or before the target_date.
    """
    balance = ZERO
    code_str = str(account_code)
    for transaction in book.transactions:
        post_date = transaction.post_date
        if isinstance(post_date, date) and post_date <= target_date:
            for split in transaction.splits:
                if split.account.code == code_str:
                    balance += Decimal(str(split.value))
    return balance


def _prepare_ne_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return NE-bilaga ruta→amount mapping.

    Revenue accounts (30xx) are credit accounts in GnuCash (negative values).
    Cost accounts (50xx-69xx, 79xx) are debit accounts (positive values).
    We negate revenue to show positive and keep costs positive as-is.
    """
    start_date, end_date = _get_fiscal_year_dates(fiscal_year)

    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        splits = _query_splits_for_fiscal_year(book, fiscal_year)
        account_totals = _aggregate_by_account(splits)

        rutor: dict[str, Decimal] = {}

        for ruta, config in NE_RUTA_CONFIG.items():
            ruta_type = config["type"]

            if ruta_type == "prefix":
                raw = _sum_by_prefix(account_totals, config["prefixes"])
                # Revenue accounts are negative in GnuCash; negate for display
                rutor[ruta] = _round_ore(-raw)

            elif ruta_type == "range":
                raw = _sum_by_range(account_totals, config["ranges"])
                # Cost accounts are positive in GnuCash; keep as-is
                rutor[ruta] = _round_ore(raw)

            elif ruta_type == "opening_balance":
                # Balance at the day before fiscal year start
                day_before_start = date(fiscal_year - 1, 12, 31)
                balance = _compute_account_balance_at_date(
                    book, config["account"], day_before_start
                )
                # Equity account 2010 is credit (negative in GnuCash); negate
                rutor[ruta] = _round_ore(-balance)

            elif ruta_type == "closing_balance":
                balance = _compute_account_balance_at_date(
                    book, config["account"], end_date
                )
                rutor[ruta] = _round_ore(-balance)

        # R7 = R1 + R2 - R5 - R6
        rutor["R7"] = _round_ore(
            rutor.get("R1", ZERO)
            + rutor.get("R2", ZERO)
            - rutor.get("R5", ZERO)
            - rutor.get("R6", ZERO)
        )

    resultat_rows = []
    for ruta in ["R1", "R2", "R5", "R6", "R7"]:
        resultat_rows.append({
            "ruta": ruta,
            "description": NE_RUTA_CONFIG[ruta]["description"],
            "amount": rutor.get(ruta, ZERO),
        })

    balans_rows = []
    for ruta in ["B1", "B4"]:
        balans_rows.append({
            "ruta": ruta,
            "description": NE_RUTA_CONFIG[ruta]["description"],
            "amount": rutor.get(ruta, ZERO),
        })

    return {
        "report_title": "NE-bilaga",
        "reference": "INK1 NE-bilaga",
        "fiscal_year": fiscal_year,
        "resultat_rows": resultat_rows,
        "balans_rows": balans_rows,
        "rutor": rutor,
    }


# ---------------------------------------------------------------------------
# Grundbok data preparation
# ---------------------------------------------------------------------------


def _prepare_grundbok_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return chronological journal data.

    Flattens transactions to split-level rows sorted by date and
    verification number, then computes grand totals for debet/kredit.
    """
    start_date, end_date = _get_fiscal_year_dates(fiscal_year)

    rows: list[dict[str, Any]] = []

    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        for transaction in book.transactions:
            post_date = transaction.post_date
            if not (isinstance(post_date, date) and start_date <= post_date <= end_date):
                continue

            for split in transaction.splits:
                amount = Decimal(str(split.value))
                debet = _round_ore(amount) if amount > ZERO else ZERO
                kredit = _round_ore(-amount) if amount < ZERO else ZERO

                rows.append({
                    "verifikation": transaction.num or "",
                    "datum": post_date,
                    "text": transaction.description or "",
                    "konto_code": split.account.code or "",
                    "konto_name": split.account.name or "",
                    "debet": debet,
                    "kredit": kredit,
                })

    # Sort by date, then by verification number
    rows.sort(key=lambda r: (r["datum"], r["verifikation"]))

    grand_total_debet = sum((r["debet"] for r in rows), ZERO)
    grand_total_kredit = sum((r["kredit"] for r in rows), ZERO)

    return {
        "report_title": "Grundbok",
        "fiscal_year": fiscal_year,
        "rows": rows,
        "grand_total_debet": _round_ore(grand_total_debet),
        "grand_total_kredit": _round_ore(grand_total_kredit),
    }


# ---------------------------------------------------------------------------
# Huvudbok data preparation
# ---------------------------------------------------------------------------


def _prepare_huvudbok_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return per-account ledger data.

    For each account with activity in the fiscal year:
    - Compute opening balance (all splits before fiscal year start)
    - List all transactions within the fiscal year
    - Compute closing balance and subtotals
    Accounts are sorted by account number.
    """
    start_date, end_date = _get_fiscal_year_dates(fiscal_year)
    day_before_start = date(fiscal_year - 1, 12, 31)

    account_data: dict[str, dict[str, Any]] = {}

    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        # First pass: collect all accounts with fiscal year activity
        for transaction in book.transactions:
            post_date = transaction.post_date
            if not isinstance(post_date, date):
                continue

            for split in transaction.splits:
                code = split.account.code
                if not code:
                    continue

                if code not in account_data:
                    account_data[code] = {
                        "code": code,
                        "name": split.account.name or "",
                        "opening_balance": ZERO,
                        "transactions": [],
                        "subtotal_debet": ZERO,
                        "subtotal_kredit": ZERO,
                    }

                amount = Decimal(str(split.value))

                if post_date <= day_before_start:
                    # Contributes to opening balance
                    account_data[code]["opening_balance"] += amount
                elif start_date <= post_date <= end_date:
                    debet = _round_ore(amount) if amount > ZERO else ZERO
                    kredit = _round_ore(-amount) if amount < ZERO else ZERO

                    account_data[code]["transactions"].append({
                        "datum": post_date,
                        "verifikation": transaction.num or "",
                        "text": transaction.description or "",
                        "debet": debet,
                        "kredit": kredit,
                    })
                    account_data[code]["subtotal_debet"] += debet
                    account_data[code]["subtotal_kredit"] += kredit

    # Only keep accounts that have fiscal-year activity
    active_accounts = {
        code: data
        for code, data in account_data.items()
        if data["transactions"]
    }

    # Compute closing balances and round
    for data in active_accounts.values():
        data["opening_balance"] = _round_ore(data["opening_balance"])
        data["subtotal_debet"] = _round_ore(data["subtotal_debet"])
        data["subtotal_kredit"] = _round_ore(data["subtotal_kredit"])
        data["closing_balance"] = _round_ore(
            data["opening_balance"]
            + data["subtotal_debet"]
            - data["subtotal_kredit"]
        )
        # Sort transactions within account by date
        data["transactions"].sort(key=lambda t: (t["datum"], t["verifikation"]))

    # Sort accounts by code
    sorted_accounts = sorted(active_accounts.values(), key=lambda a: a["code"])

    return {
        "report_title": "Huvudbok",
        "fiscal_year": fiscal_year,
        "accounts": sorted_accounts,
    }


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _render_template(
    template_name: str,
    report_data: dict[str, Any],
    company_info: CompanyInfo,
) -> str:
    """Render an HTML template with report data and company info.

    Args:
        template_name: Filename of the Jinja2 template.
        report_data: Report-specific data dictionary.
        company_info: Company metadata for headers.

    Returns:
        Rendered HTML string.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )

    # Custom filter for Swedish currency formatting
    def format_sek(value: Decimal) -> str:
        """Format a Decimal as Swedish currency (space as thousands separator)."""
        if value == ZERO:
            return "0,00"
        # Format with 2 decimal places, Swedish style
        sign = "-" if value < 0 else ""
        abs_val = abs(value)
        integer_part = int(abs_val)
        decimal_part = abs_val - integer_part
        # Add space thousands separator
        int_str = f"{integer_part:,}".replace(",", " ")
        dec_str = f"{decimal_part:.2f}"[1:]  # ".XX"
        dec_str = dec_str.replace(".", ",")
        return f"{sign}{int_str}{dec_str}"

    env.filters["sek"] = format_sek

    template = env.get_template(template_name)
    return template.render(
        company=company_info,
        **report_data,
    )


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def _html_to_pdf(html_content: str, output_path: Path) -> None:
    """Convert rendered HTML to an A4 PDF file.

    Args:
        html_content: Complete HTML string to render.
        output_path: Path where the PDF file will be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_doc = weasyprint.HTML(string=html_content, base_url=str(_TEMPLATES_DIR))
    html_doc.write_pdf(str(output_path))
