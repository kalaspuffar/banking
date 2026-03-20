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

import functools
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

import jinja2
import piecash
import weasyprint

logger = logging.getLogger(__name__)

from bookkeeping.models import CompanyInfo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_REPORT_TYPES = ("vat", "ne", "journal", "ledger")

ZERO = Decimal("0.00")

# SKV 4700 box mapping: box number → list of account codes.
# Each entry maps a Skatteverket form box (ruta) to the accounts whose
# totals feed it.
VAT_BOX_ACCOUNTS: dict[str, list[int]] = {
    "05": [3010],       # Momspliktig försäljning 25%
    "06": [3011],       # Momspliktig försäljning 12%
    "07": [3012],       # Momspliktig försäljning 6%
    "08": [3040],       # Momsfri försäljning
    "10": [2610],       # Utgående moms 25%
    "11": [2620],       # Utgående moms 12%
    "12": [2630],       # Utgående moms 6%
    "48": [2640],       # Ingående moms
}

VAT_BOX_DESCRIPTIONS: dict[str, str] = {
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

# INK1 NE-bilaga box mapping: box → (type, account ranges).
# type is "prefix" for account prefix match, "range" for range match,
# "exact" for single account, or "computed" for derived values.
NE_BOX_CONFIG: dict[str, dict[str, Any]] = {
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
        report_type: One of "vat", "ne", "journal", "ledger".
            Note: "all" is not handled here — it should be handled by the CLI
            caller by looping over all four individual types.
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
        "vat": prepare_vat_data,
        "ne": prepare_ne_data,
        "journal": prepare_journal_data,
        "ledger": prepare_ledger_data,
    }

    template_names = {
        "vat": "momsdeklaration.html",
        "ne": "ne_bilaga.html",
        "journal": "grundbok.html",
        "ledger": "huvudbok.html",
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


def aggregate_by_account(
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


def sum_by_prefix(
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


def sum_by_range(
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


def sum_by_exact_accounts(
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


def round_ore(amount: Decimal) -> Decimal:
    """Round to öre (2 decimal places) using banker's rounding."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


# ---------------------------------------------------------------------------
# VAT return (momsdeklaration) data preparation
# ---------------------------------------------------------------------------


def prepare_vat_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return VAT return box→amount mapping.

    Revenue accounts (30xx) store credits as negative in GnuCash, so
    we negate them to display as positive amounts on the form. VAT output
    accounts (26xx) are also credit accounts (negative). Input VAT (2640)
    is a debit account (positive).
    """
    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        splits = _query_splits_for_fiscal_year(book, fiscal_year)
        account_totals = aggregate_by_account(splits)

    if not account_totals:
        logger.warning(
            "No transactions found for fiscal year %d. "
            "The momsdeklaration report will contain all-zero values.",
            fiscal_year,
        )

    boxes: dict[str, Decimal] = {}
    for box, accounts in VAT_BOX_ACCOUNTS.items():
        raw = sum_by_exact_accounts(account_totals, accounts)
        # Revenue and output VAT accounts are credit accounts in GnuCash
        # (stored as negative). Negate to show positive on the form.
        # Input VAT (box 48, account 2640) is a debit account (positive).
        if box in ("05", "06", "07", "08", "10", "11", "12"):
            boxes[box] = round_ore(-raw)
        else:
            boxes[box] = round_ore(raw)

    # Box 49: output VAT minus input VAT
    output_vat = (
        boxes.get("10", ZERO) + boxes.get("11", ZERO) + boxes.get("12", ZERO)
    )
    input_vat = boxes.get("48", ZERO)
    boxes["49"] = round_ore(output_vat - input_vat)

    box_rows = []
    for box_num in ["05", "06", "07", "08", "10", "11", "12", "48", "49"]:
        amount = boxes.get(box_num, ZERO)
        box_rows.append({
            "box": box_num,
            "description": VAT_BOX_DESCRIPTIONS[box_num],
            "amount": amount,
        })

    return {
        "report_title": "Momsdeklaration",
        "reference": "SKV 4700",
        "fiscal_year": fiscal_year,
        "box_rows": box_rows,
        "boxes": boxes,
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


def prepare_ne_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return NE-bilaga box→amount mapping.

    Revenue accounts (30xx) are credit accounts in GnuCash (negative values).
    Cost accounts (50xx-69xx, 79xx) are debit accounts (positive values).
    We negate revenue to show positive and keep costs positive as-is.
    """
    start_date, end_date = _get_fiscal_year_dates(fiscal_year)

    with piecash.open_book(str(gnucash_book_path), readonly=True, open_if_lock=True) as book:
        splits = _query_splits_for_fiscal_year(book, fiscal_year)
        account_totals = aggregate_by_account(splits)

        if not account_totals:
            logger.warning(
                "No transactions found for fiscal year %d. "
                "The NE-bilaga report will contain all-zero values.",
                fiscal_year,
            )

        boxes: dict[str, Decimal] = {}

        for box, config in NE_BOX_CONFIG.items():
            box_type = config["type"]

            if box_type == "prefix":
                raw = sum_by_prefix(account_totals, config["prefixes"])
                # Revenue accounts are negative in GnuCash; negate for display
                boxes[box] = round_ore(-raw)

            elif box_type == "range":
                raw = sum_by_range(account_totals, config["ranges"])
                # Cost accounts are positive in GnuCash; keep as-is
                boxes[box] = round_ore(raw)

            elif box_type == "opening_balance":
                # Balance at the day before fiscal year start
                day_before_start = date(fiscal_year - 1, 12, 31)
                balance = _compute_account_balance_at_date(
                    book, config["account"], day_before_start
                )
                # Equity account 2010 is credit (negative in GnuCash); negate
                boxes[box] = round_ore(-balance)

            elif box_type == "closing_balance":
                balance = _compute_account_balance_at_date(
                    book, config["account"], end_date
                )
                boxes[box] = round_ore(-balance)

        # R7 = R1 + R2 - R5 - R6
        boxes["R7"] = round_ore(
            boxes.get("R1", ZERO)
            + boxes.get("R2", ZERO)
            - boxes.get("R5", ZERO)
            - boxes.get("R6", ZERO)
        )

    income_rows = []
    for box in ["R1", "R2", "R5", "R6", "R7"]:
        income_rows.append({
            "box": box,
            "description": NE_BOX_CONFIG[box]["description"],
            "amount": boxes.get(box, ZERO),
        })

    balance_rows = []
    for box in ["B1", "B4"]:
        balance_rows.append({
            "box": box,
            "description": NE_BOX_CONFIG[box]["description"],
            "amount": boxes.get(box, ZERO),
        })

    return {
        "report_title": "NE-bilaga",
        "reference": "INK1 NE-bilaga",
        "fiscal_year": fiscal_year,
        "income_rows": income_rows,
        "balance_rows": balance_rows,
        "boxes": boxes,
    }


# ---------------------------------------------------------------------------
# Journal (grundbok) data preparation
# ---------------------------------------------------------------------------


def prepare_journal_data(
    gnucash_book_path: Path, fiscal_year: int
) -> dict[str, Any]:
    """Query GnuCash and return chronological journal data.

    Flattens transactions to split-level rows sorted by date and
    verification number, then computes grand totals for debit/credit.
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
                debit = round_ore(amount) if amount > ZERO else ZERO
                credit = round_ore(-amount) if amount < ZERO else ZERO

                rows.append({
                    "verification": transaction.num or "",
                    "date": post_date,
                    "text": transaction.description or "",
                    "account_code": split.account.code or "",
                    "account_name": split.account.name or "",
                    "debit": debit,
                    "credit": credit,
                })

    if not rows:
        logger.warning(
            "No transactions found for fiscal year %d. "
            "The journal report will be empty.",
            fiscal_year,
        )

    # Sort by date, then by verification number.
    # Known limitation: page-level subtotals are not implemented. The spec
    # mentions "page totals and grand totals", but page totals require
    # WeasyPrint CSS paged media features that are non-trivial to implement.
    # For a small enskild firma (~200-400 transactions/year), grand totals
    # alone are sufficient.
    rows.sort(key=lambda r: (r["date"], r["verification"]))

    grand_total_debit = sum((r["debit"] for r in rows), ZERO)
    grand_total_credit = sum((r["credit"] for r in rows), ZERO)

    return {
        "report_title": "Grundbok",
        "fiscal_year": fiscal_year,
        "rows": rows,
        "grand_total_debit": round_ore(grand_total_debit),
        "grand_total_credit": round_ore(grand_total_credit),
    }


# ---------------------------------------------------------------------------
# Ledger (huvudbok) data preparation
# ---------------------------------------------------------------------------


def prepare_ledger_data(
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
        # Single pass over all transactions: opening balances are computed
        # from transactions with post_date <= day_before_start, which is O(n)
        # over the full book history. For a small enskild firma (~200-400
        # txns/year) this is acceptable. If performance becomes an issue with
        # many years of data, consider precomputing opening balances in a
        # separate pass or caching them.
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
                        "subtotal_debit": ZERO,
                        "subtotal_credit": ZERO,
                    }

                amount = Decimal(str(split.value))

                if post_date <= day_before_start:
                    # Contributes to opening balance
                    account_data[code]["opening_balance"] += amount
                elif start_date <= post_date <= end_date:
                    debit = round_ore(amount) if amount > ZERO else ZERO
                    credit = round_ore(-amount) if amount < ZERO else ZERO

                    account_data[code]["transactions"].append({
                        "date": post_date,
                        "verification": transaction.num or "",
                        "text": transaction.description or "",
                        "debit": debit,
                        "credit": credit,
                    })
                    account_data[code]["subtotal_debit"] += debit
                    account_data[code]["subtotal_credit"] += credit

    # Only keep accounts that have fiscal-year activity
    active_accounts = {
        code: data
        for code, data in account_data.items()
        if data["transactions"]
    }

    # Compute closing balances and round
    for data in active_accounts.values():
        data["opening_balance"] = round_ore(data["opening_balance"])
        data["subtotal_debit"] = round_ore(data["subtotal_debit"])
        data["subtotal_credit"] = round_ore(data["subtotal_credit"])
        data["closing_balance"] = round_ore(
            data["opening_balance"]
            + data["subtotal_debit"]
            - data["subtotal_credit"]
        )
        # Sort transactions within account by date
        data["transactions"].sort(key=lambda t: (t["date"], t["verification"]))

    if not active_accounts:
        logger.warning(
            "No accounts with activity found for fiscal year %d. "
            "The ledger report will be empty.",
            fiscal_year,
        )

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


def format_sek(value: Decimal) -> str:
    """Format a Decimal as Swedish currency (space as thousands separator).

    Uses string-based decimal splitting to avoid floating-point precision
    issues that can arise with very large Decimal values when using
    float-style formatting.

    Args:
        value: Amount in SEK as a Decimal.

    Returns:
        Formatted string with comma as decimal separator and space as
        thousands separator (e.g., "1 234 567,89").
    """
    if value == ZERO:
        return "0,00"

    sign = "-" if value < 0 else ""
    abs_val = abs(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    int_part, dec_part = str(abs_val).split(".")

    # Add space as thousands separator by iterating in reverse
    int_str = ""
    for i, ch in enumerate(reversed(int_part)):
        if i > 0 and i % 3 == 0:
            int_str = " " + int_str
        int_str = ch + int_str

    return f"{sign}{int_str},{dec_part}"


@functools.lru_cache(maxsize=1)
def _get_jinja_env() -> jinja2.Environment:
    """Create and cache the Jinja2 environment with custom filters.

    Cached so that generating multiple reports in sequence (e.g., type="all"
    in the CLI) reuses a single environment instance.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["sek"] = format_sek
    return env


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
    env = _get_jinja_env()
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
