"""CLI entry point for the bookkeeping tool.

Provides the full argparse-based command-line interface with subcommands
for importing bank transactions, generating reports, managing categorisation
rules, viewing/setting configuration, and first-time setup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bookkeeping.config import ConfigManager
from bookkeeping.models import CSVParseError, GnuCashError

# Exit codes per specification
EXIT_SUCCESS = 0
EXIT_CSV_ERROR = 1
EXIT_GNUCASH_ERROR = 2
EXIT_USER_CANCELLED = 3

# Separate constant for usage errors to avoid conflating with CSV errors.
# The numeric value is still 1 (standard convention for CLI usage errors),
# but the distinct name makes intent clear at each call-site.
EXIT_USAGE_ERROR = 1

# Valid configuration keys per specification (section 5.4).
_VALID_CONFIG_KEYS: frozenset[str] = frozenset({
    "gnucash_book_path",
    "company_name",
    "org_number",
    "company_address",
})

# Default paths
_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "bookkeeping"
_DEFAULT_DB_PATH = _DEFAULT_DATA_DIR / "rules.db"
_DEFAULT_OUTPUT_DIR = Path("rapporter")


def _get_config_manager() -> ConfigManager:
    """Open the ConfigManager for the default rules.db location."""
    return ConfigManager(_DEFAULT_DB_PATH)


def _resolve_book_path(args_book: str | None) -> Path:
    """Resolve the GnuCash book path from CLI flag or config.

    Args:
        args_book: Value of the ``--book`` flag, or None.

    Returns:
        Resolved Path to the GnuCash book file.

    Raises:
        SystemExit: If no book path can be resolved.
    """
    if args_book:
        book_path = Path(args_book)
    else:
        with _get_config_manager() as cm:
            stored = cm.get("gnucash_book_path")
        if not stored:
            print(
                "Error: No GnuCash book path configured. "
                "Run 'bookkeeping init' or use --book.",
                file=sys.stderr,
            )
            sys.exit(EXIT_GNUCASH_ERROR)
        book_path = Path(stored)

    if not book_path.is_file():
        print(
            f"Error: GnuCash book not found: {book_path}",
            file=sys.stderr,
        )
        sys.exit(EXIT_GNUCASH_ERROR)

    return book_path


def _load_bas_accounts() -> list:
    """Load BAS 2023 accounts from the bundled bas2023.csv file.

    Parses the BAS CSV (which has a non-standard layout) and returns a list
    of AccountItem objects suitable for the GTK4 account selector. Only
    4-digit "underkonton" (sub-accounts) are included.

    Returns:
        List of AccountItem objects sorted by account code.
    """
    import csv
    from decimal import Decimal

    from bookkeeping.gtk_app import AccountItem

    bas_csv_path = Path(__file__).parent.parent / "bas2023.csv"
    if not bas_csv_path.is_file():
        print(
            f"Warning: BAS 2023 CSV not found at {bas_csv_path}. "
            "Account selector will be empty.",
            file=sys.stderr,
        )
        return []

    accounts: list[AccountItem] = []
    with bas_csv_path.open(mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            code_str = row[6].strip() if row[6] else ""
            name = row[7].strip() if row[7] else ""
            # Only include 4-digit account codes (underkonton)
            if len(code_str) == 4 and code_str.isdigit() and name:
                accounts.append(AccountItem(
                    code=int(code_str),
                    name=name,
                    vat_rate=Decimal("0.00"),
                ))

    accounts.sort(key=lambda a: a.code)
    return accounts


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _handle_init(args: argparse.Namespace) -> None:
    """Run the first-time setup wizard."""
    _DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _get_config_manager() as cm:
        # Resolve default book path for the prompt
        default_book = cm.get("gnucash_book_path")
        if not default_book:
            found = cm.find_default_book_path()
            default_book = str(found) if found else ""

        current_name = cm.get("company_name", "")
        current_org = cm.get("org_number", "")
        current_addr = cm.get("company_address", "")

        print("bookkeeping — First-time setup\n")

        book_path = _prompt_required(
            "GnuCash book path", default_book
        )

        # Validate the GnuCash book path
        if book_path:
            book = Path(book_path)
            if not book.is_file():
                print(
                    f"Warning: File not found: {book}. "
                    "You can update this later with 'bookkeeping config set gnucash_book_path <path>'.",
                    file=sys.stderr,
                )
            cm.set("gnucash_book_path", book_path)

        company_name = _prompt_with_default("Company name", current_name)
        if company_name:
            cm.set("company_name", company_name)

        org_number = _prompt_with_default("Organisationsnummer", current_org)
        if org_number:
            cm.set("org_number", org_number)

        address = _prompt_with_default("Company address", current_addr)
        if address:
            cm.set("company_address", address)

    print("\nSetup complete. Configuration saved to:", _DEFAULT_DB_PATH)


def _prompt_with_default(prompt_text: str, default: str) -> str:
    """Prompt the user for input with an optional default value.

    Args:
        prompt_text: The prompt label to display.
        default: The default value shown in brackets.

    Returns:
        User input, or the default if the user presses Enter.
    """
    if default:
        user_input = input(f"  {prompt_text} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"  {prompt_text}: ").strip()


def _prompt_required(prompt_text: str, default: str) -> str:
    """Prompt the user for input, requiring a non-empty value.

    Re-prompts until a non-empty value is provided or a default exists.

    Args:
        prompt_text: The prompt label to display.
        default: The default value shown in brackets.

    Returns:
        A non-empty string (user input or the default).
    """
    while True:
        value = _prompt_with_default(prompt_text, default)
        if value:
            return value
        print(f"    (required) Please enter a value for {prompt_text}.")


def _handle_import(args: argparse.Namespace) -> None:
    """Run the import pipeline."""
    from decimal import Decimal

    from bookkeeping.categorizer import apply_aliases, suggest_categorization
    from bookkeeping.csv_parser import parse_bank_csv
    from bookkeeping.dedup import filter_duplicates
    from bookkeeping.models import BankTransaction, CategorizationSuggestion
    from bookkeeping.rules_db import RulesDatabase

    csv_path = Path(args.csv_file)
    if not csv_path.is_file():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(EXIT_CSV_ERROR)

    transactions = parse_bank_csv(csv_path)
    print(f"Parsed {len(transactions)} transactions from {csv_path.name}")

    book_path = _resolve_book_path(args.book)

    new_transactions, duplicates = filter_duplicates(transactions, book_path)
    print(
        f"  {len(new_transactions)} new, {len(duplicates)} duplicates"
    )

    if not new_transactions:
        print("No new transactions to import.")
        return

    with RulesDatabase(_DEFAULT_DB_PATH) as rules_db:
        # Apply text aliases before categorization
        aliases = rules_db.list_aliases()
        if aliases:
            aliased_transactions: list[BankTransaction] = []
            for t in new_transactions:
                replacement = apply_aliases(t.text, aliases)
                if replacement is not None:
                    # Create new frozen instance with display_text set
                    t = BankTransaction(
                        booking_date=t.booking_date,
                        value_date=t.value_date,
                        verification_number=t.verification_number,
                        text=t.text,
                        amount=t.amount,
                        balance=t.balance,
                        display_text=replacement,
                    )
                aliased_transactions.append(t)
            new_transactions = aliased_transactions

        raw_suggestions = [
            suggest_categorization(t, rules_db) for t in new_transactions
        ]

    # Wrap unmatched transactions in a "none" confidence placeholder so that
    # every entry in the list is a CategorizationSuggestion (the GTK GUI's
    # TransactionRow requires a non-None suggestion object).
    suggestions: list[CategorizationSuggestion] = []
    for txn, raw in zip(new_transactions, raw_suggestions):
        if raw is not None:
            suggestions.append(raw)
        else:
            suggestions.append(CategorizationSuggestion(
                transaction=txn,
                debit_account=0,
                credit_account=0,
                vat_rate=Decimal("0.00"),
                vat_account=None,
                confidence="none",
                rule_id=None,
            ))

    categorized = sum(1 for s in suggestions if s.confidence != "none")
    print(f"  {categorized}/{len(suggestions)} categorized by rules")

    if args.dry_run:
        _print_dry_run_summary(new_transactions, suggestions)
        return

    if args.no_gui:
        _handle_import_no_gui(
            new_transactions, suggestions, book_path, csv_path
        )
        return

    # Full GUI mode
    _handle_import_gui(
        new_transactions, suggestions, book_path, csv_path,
        new_count=len(new_transactions),
        duplicate_count=len(duplicates),
    )


def _print_dry_run_summary(
    transactions: list,
    suggestions: list,
) -> None:
    """Print a summary of what would be imported without making changes."""
    print("\n--- Dry-run summary ---")
    for txn, suggestion in zip(transactions, suggestions):
        status = "→ categorized" if (suggestion and suggestion.confidence != "none") else "→ uncategorized"
        print(f"  {txn.booking_date}  {txn.amount:>10}  {txn.text[:40]:<40}  {status}")
    print(f"\nTotal: {len(transactions)} transactions would be imported.")


def _handle_import_no_gui(
    transactions: list,
    suggestions: list,
    book_path: Path,
    csv_path: Path,
) -> None:
    """CLI-only import mode with text-based confirmation."""
    print("\n--- Transactions to import ---")
    for i, (txn, suggestion) in enumerate(zip(transactions, suggestions), 1):
        if suggestion and suggestion.confidence != "none":
            acct = f"debit={suggestion.debit_account} credit={suggestion.credit_account}"
        else:
            acct = "uncategorized"
        print(f"  {i}. {txn.booking_date}  {txn.amount:>10}  {txn.text[:40]:<40}  {acct}")

    try:
        confirm = input("\nProceed with import? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nImport cancelled.", file=sys.stderr)
        sys.exit(EXIT_USER_CANCELLED)

    if confirm != "y":
        print("Import cancelled.")
        sys.exit(EXIT_USER_CANCELLED)

    _write_and_log(transactions, suggestions, book_path, csv_path)


def _handle_import_gui(
    transactions: list,
    suggestions: list,
    book_path: Path,
    csv_path: Path,
    new_count: int = 0,
    duplicate_count: int = 0,
) -> None:
    """Launch the GTK4 verification GUI for import."""
    try:
        from bookkeeping.gtk_app import BookkeepingApp
    except ImportError:
        print(
            "Error: GTK4 is not available. Use --no-gui for CLI-only mode.",
            file=sys.stderr,
        )
        sys.exit(EXIT_GNUCASH_ERROR)

    from bookkeeping.categorizer import save_rule
    from bookkeeping.gnucash_writer import write_transactions
    from bookkeeping.rules_db import RulesDatabase

    app = BookkeepingApp()

    accounts = _load_bas_accounts()

    def on_save(entries: list) -> None:
        result = write_transactions(book_path, entries)
        print(f"Wrote {result.transactions_written} transactions to GnuCash.")
        if result.errors:
            for err in result.errors:
                print(f"  Error: {err}", file=sys.stderr)
        _log_import(
            csv_path,
            transactions_total=len(transactions),
            transactions_new=result.transactions_written,
            transactions_dup=duplicate_count,
            transactions_error=len(result.errors),
        )

    def on_save_rules(rules_data: list) -> None:
        with RulesDatabase(_DEFAULT_DB_PATH) as rules_db:
            for rule_info in rules_data:
                save_rule(
                    rules_db,
                    pattern=rule_info["pattern"],
                    debit_account=rule_info["debit_account"],
                    credit_account=rule_info["credit_account"],
                    vat_rate=rule_info["vat_rate"],
                    amount=rule_info["amount"],
                )

    app.configure(
        suggestions=suggestions,
        accounts=accounts,
        new_count=new_count,
        duplicate_count=duplicate_count,
        on_save=on_save,
        on_save_rules=on_save_rules,
    )
    app.run()


def _write_and_log(
    transactions: list,
    suggestions: list,
    book_path: Path,
    csv_path: Path,
) -> None:
    """Write transactions to GnuCash and log the import."""
    from bookkeeping.gnucash_writer import write_transactions
    from bookkeeping.journal import build_journal_entry

    entries = []
    skipped_count = 0
    errors_count = 0
    for txn, suggestion in zip(transactions, suggestions):
        if suggestion and suggestion.confidence != "none":
            try:
                entry = build_journal_entry(
                    verification_number=txn.verification_number,
                    booking_date=txn.booking_date,
                    description=txn.text,
                    amount=txn.amount,
                    debit_account=suggestion.debit_account,
                    credit_account=suggestion.credit_account,
                    vat_rate=suggestion.vat_rate,
                    vat_account=suggestion.vat_account,
                )
                entries.append(entry)
            except Exception as exc:
                print(f"  Error building entry for {txn.text}: {exc}", file=sys.stderr)
                errors_count += 1
        else:
            skipped_count += 1

    if skipped_count:
        print(
            f"Warning: {skipped_count} uncategorized transaction(s) will be skipped.",
            file=sys.stderr,
        )

    if entries:
        result = write_transactions(book_path, entries)
        print(f"Wrote {result.transactions_written} transactions to GnuCash.")
        errors_count += len(result.errors)
    else:
        print("No categorized transactions to write.")

    _log_import(
        csv_path,
        transactions_total=len(transactions),
        transactions_new=len(entries),
        transactions_dup=0,
        transactions_error=errors_count,
    )


def _log_import(
    csv_path: Path,
    transactions_total: int,
    transactions_new: int,
    transactions_dup: int,
    transactions_error: int,
) -> None:
    """Record an import operation in the import_log table via RulesDatabase."""
    from bookkeeping.rules_db import RulesDatabase

    try:
        with RulesDatabase(_DEFAULT_DB_PATH) as db:
            db.log_import(
                csv_filename=csv_path.name,
                transactions_total=transactions_total,
                transactions_new=transactions_new,
                transactions_dup=transactions_dup,
                transactions_error=transactions_error,
            )
    except Exception as exc:
        print(f"Warning: Failed to log import: {exc}", file=sys.stderr)


def _handle_report(args: argparse.Namespace) -> None:
    """Generate PDF reports."""
    from bookkeeping.reports import VALID_REPORT_TYPES, generate_report

    book_path = _resolve_book_path(args.book)
    fiscal_year = args.year

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    with _get_config_manager() as cm:
        company_info = cm.get_company_info(fiscal_year)

    report_types = list(VALID_REPORT_TYPES) if args.type == "all" else [args.type]

    for report_type in report_types:
        filename_map = {
            "vat": f"momsdeklaration_{fiscal_year}.pdf",
            "ne": f"ne_bilaga_{fiscal_year}.pdf",
            "journal": f"grundbok_{fiscal_year}.pdf",
            "ledger": f"huvudbok_{fiscal_year}.pdf",
        }
        output_path = output_dir / filename_map[report_type]
        result_path = generate_report(
            report_type=report_type,
            gnucash_book_path=book_path,
            fiscal_year=fiscal_year,
            output_path=output_path,
            company_info=company_info,
        )
        print(f"Generated: {result_path}")


def _handle_rules(args: argparse.Namespace) -> None:
    """Handle rules subcommands."""
    if args.rules_command == "list":
        _handle_rules_list()
    elif args.rules_command == "delete":
        _handle_rules_delete(args.rule_id)
    elif args.rules_command == "export":
        _handle_rules_export(args.file)
    elif args.rules_command == "import":
        _handle_rules_import(args.file)
    elif args.rules_command == "create":
        _handle_rules_create(args)
    else:
        print("Error: Specify a rules subcommand (list, delete, export, import, create).", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)


def _handle_rules_list() -> None:
    """Display all rules in a formatted table."""
    from bookkeeping.rules_db import RulesDatabase

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        rules = db.list_rules()

    if not rules:
        print("No rules found.")
        return

    header = f"{'ID':>4}  {'Pattern':<30}  {'Type':<8}  {'Debit':>5}  {'Credit':>6}  {'VAT':>5}  {'Uses':>5}"
    print(header)
    print("-" * len(header))
    for rule in rules:
        print(
            f"{rule.id:>4}  {rule.pattern[:30]:<30}  {rule.match_type:<8}  "
            f"{rule.debit_account:>5}  {rule.credit_account:>6}  "
            f"{rule.vat_rate:>5}  {rule.use_count:>5}"
        )


def _handle_rules_delete(rule_id: int) -> None:
    """Delete a rule with confirmation."""
    from bookkeeping.rules_db import RulesDatabase

    try:
        confirm = input(f"Delete rule {rule_id}? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if confirm != "y":
        print("Cancelled.")
        return

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        db.delete_rule(rule_id)
    print(f"Rule {rule_id} deleted.")


def _handle_rules_export(filepath: str) -> None:
    """Export rules to a JSON file."""
    from bookkeeping.rules_db import RulesDatabase

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        db.export_rules(Path(filepath))
    print(f"Rules exported to {filepath}")


def _handle_rules_import(filepath: str) -> None:
    """Import rules from a JSON file."""
    from bookkeeping.rules_db import RulesDatabase

    path = Path(filepath)
    if not path.is_file():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        db.import_rules(path)
    print(f"Rules imported from {filepath}")


def _handle_rules_create(args: argparse.Namespace) -> None:
    """Create a new categorization rule from CLI arguments."""
    from decimal import Decimal

    from bookkeeping.categorizer import save_rule
    from bookkeeping.rules_db import RulesDatabase

    vat_rate = Decimal(args.vat_rate)

    # save_rule needs an amount to determine VAT account direction.
    # For CLI-created rules, default to expense (negative) since most
    # manually created rules are for expense categorization.
    amount = Decimal("-1")

    with RulesDatabase(_DEFAULT_DB_PATH) as rules_db:
        save_rule(
            rules_db,
            pattern=args.pattern,
            debit_account=args.debit_account,
            credit_account=args.credit_account,
            vat_rate=vat_rate,
            amount=amount,
            match_type=args.match_type,
        )
    print(
        f"Rule created: '{args.pattern}' → "
        f"debit={args.debit_account}, credit={args.credit_account}, "
        f"vat={args.vat_rate}, type={args.match_type}"
    )


def _handle_alias(args: argparse.Namespace) -> None:
    """Handle alias subcommands."""
    if args.alias_command == "list":
        _handle_alias_list()
    elif args.alias_command == "add":
        _handle_alias_add(args.pattern, args.replacement)
    elif args.alias_command == "delete":
        _handle_alias_delete(args.alias_id)
    else:
        print(
            "Error: Specify an alias subcommand (list, add, delete).",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)


def _handle_alias_list() -> None:
    """Display all text aliases in a formatted table."""
    from bookkeeping.rules_db import RulesDatabase

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        aliases = db.list_aliases()

    if not aliases:
        print("Inga alias konfigurerade.")
        return

    header = f"{'ID':>4}  {'Pattern':<30}  {'Replacement':<30}"
    print(header)
    print("-" * len(header))
    for alias in aliases:
        print(
            f"{alias.id:>4}  {alias.pattern[:30]:<30}  "
            f"{alias.replacement[:30]:<30}"
        )


def _handle_alias_add(pattern: str, replacement: str) -> None:
    """Add or update a text alias."""
    from bookkeeping.rules_db import RulesDatabase

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        db.add_alias(pattern, replacement)
    print(f"Alias saved: '{pattern}' → '{replacement}'")


def _handle_alias_delete(alias_id: int) -> None:
    """Delete a text alias by ID."""
    from bookkeeping.rules_db import RulesDatabase

    with RulesDatabase(_DEFAULT_DB_PATH) as db:
        db.delete_alias(alias_id)
    print(f"Alias {alias_id} deleted.")


def _handle_config(args: argparse.Namespace) -> None:
    """Handle config subcommands."""
    if args.config_command == "show":
        _handle_config_show()
    elif args.config_command == "set":
        _handle_config_set(args.key, args.value)
    else:
        print("Error: Specify a config subcommand (show, set).", file=sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)


def _handle_config_show() -> None:
    """Display all current configuration."""
    with _get_config_manager() as cm:
        config = cm.get_all()

    if not config:
        print("No configuration set. Run 'bookkeeping init' to get started.")
        return

    max_key_len = max(len(k) for k in config)
    for key, value in config.items():
        print(f"  {key:<{max_key_len}}  {value}")


def _handle_config_set(key: str, value: str) -> None:
    """Set a configuration value after validating the key.

    Args:
        key: Configuration key (must be one of the spec-defined keys).
        value: Value to store.
    """
    if key not in _VALID_CONFIG_KEYS:
        print(
            f"Warning: '{key}' is not a recognized config key. "
            f"Valid keys: {', '.join(sorted(_VALID_CONFIG_KEYS))}",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)

    with _get_config_manager() as cm:
        cm.set(key, value)
    print(f"Set {key} = {value}")


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the complete argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="bookkeeping",
        description="Swedish bookkeeping automation for GnuCash",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- init ---
    init_parser = subparsers.add_parser("init", help="First-time setup wizard")
    init_parser.set_defaults(handler=_handle_init)

    # --- import ---
    import_parser = subparsers.add_parser(
        "import", help="Import bank transactions from CSV"
    )
    import_parser.add_argument("csv_file", help="Path to the bank CSV file")
    import_parser.add_argument(
        "--book", default=None, help="Path to the GnuCash book file"
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show what would be imported without writing",
    )
    import_parser.add_argument(
        "--no-gui",
        action="store_true",
        dest="no_gui",
        help="CLI-only mode without the GTK4 GUI",
    )
    import_parser.set_defaults(handler=_handle_import)

    # --- report ---
    report_parser = subparsers.add_parser(
        "report", help="Generate PDF reports"
    )
    report_parser.add_argument(
        "type",
        choices=["vat", "ne", "journal", "ledger", "all"],
        help="Report type to generate",
    )
    report_parser.add_argument("year", type=int, help="Fiscal year (e.g. 2025)")
    report_parser.add_argument(
        "--book", default=None, help="Path to the GnuCash book file"
    )
    report_parser.add_argument(
        "--output-dir",
        default=None,
        dest="output_dir",
        help="Output directory for PDF files (default: ./rapporter/)",
    )
    report_parser.set_defaults(handler=_handle_report)

    # --- rules ---
    rules_parser = subparsers.add_parser(
        "rules", help="Manage categorization rules"
    )
    rules_sub = rules_parser.add_subparsers(dest="rules_command")

    rules_sub.add_parser("list", help="List all rules")

    delete_parser = rules_sub.add_parser("delete", help="Delete a rule by ID")
    delete_parser.add_argument("rule_id", type=int, help="Rule ID to delete")

    export_parser = rules_sub.add_parser("export", help="Export rules to JSON")
    export_parser.add_argument("file", help="Output JSON file path")

    import_rules_parser = rules_sub.add_parser(
        "import", help="Import rules from JSON"
    )
    import_rules_parser.add_argument("file", help="Input JSON file path")

    create_parser = rules_sub.add_parser(
        "create", help="Create a new categorization rule"
    )
    create_parser.add_argument(
        "--pattern", required=True, help="Text pattern to match"
    )
    create_parser.add_argument(
        "--debit-account", type=int, required=True,
        help="BAS account number to debit"
    )
    create_parser.add_argument(
        "--credit-account", type=int, required=True,
        help="BAS account number to credit"
    )
    create_parser.add_argument(
        "--vat-rate", type=str, default="0.00",
        help="VAT rate as decimal fraction (default: 0.00)"
    )
    create_parser.add_argument(
        "--match-type", choices=["exact", "contains"], default="contains",
        help="Match type (default: contains)"
    )

    rules_parser.set_defaults(handler=_handle_rules)

    # --- alias ---
    alias_parser = subparsers.add_parser(
        "alias", help="Manage transaction text aliases"
    )
    alias_sub = alias_parser.add_subparsers(dest="alias_command")

    alias_sub.add_parser("list", help="List all aliases")

    alias_add_parser = alias_sub.add_parser("add", help="Add or update an alias")
    alias_add_parser.add_argument(
        "--pattern", required=True, help="Substring to match in transaction text"
    )
    alias_add_parser.add_argument(
        "--replacement", required=True,
        help="Human-readable replacement text"
    )

    alias_delete_parser = alias_sub.add_parser(
        "delete", help="Delete an alias by ID"
    )
    alias_delete_parser.add_argument(
        "alias_id", type=int, help="Alias ID to delete"
    )

    alias_parser.set_defaults(handler=_handle_alias)

    # --- config ---
    config_parser = subparsers.add_parser(
        "config", help="View or set configuration"
    )
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show current configuration")

    set_parser = config_sub.add_parser("set", help="Set a config value")
    set_parser.add_argument("key", help="Configuration key")
    set_parser.add_argument("value", help="Configuration value")

    config_parser.set_defaults(handler=_handle_config)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the bookkeeping CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(EXIT_USAGE_ERROR)

    try:
        args.handler(args)
    except CSVParseError as exc:
        print(f"Error: CSV parse error: {exc}", file=sys.stderr)
        sys.exit(EXIT_CSV_ERROR)
    except GnuCashError as exc:
        print(f"Error: GnuCash error: {exc}", file=sys.stderr)
        sys.exit(EXIT_GNUCASH_ERROR)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(EXIT_USER_CANCELLED)
