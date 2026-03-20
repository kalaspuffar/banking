"""GTK4 verification GUI for reviewing and confirming transaction categorizations.

Provides a graphical interface where the user can inspect imported bank
transactions, accept or change suggested BAS 2023 account mappings, and
commit the final categorizations to GnuCash. No transaction is written
without explicit user confirmation.

Pure logic functions (formatting, filtering, journal entry conversion) are
importable without GTK4. The GObject model classes and GTK widgets require
PyGObject and GTK4 introspection data.

System requirements (for GUI):
    - PyGObject (``python3-gi``)
    - GTK4 introspection data (``gir1.2-gtk-4.0``)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from bookkeeping.journal import build_journal_entry
from bookkeeping.models import (
    BankTransaction,
    CategorizationSuggestion,
    GnuCashError,
    JournalEntry,
    RulesDBError,
)

# Soft import of GTK4 — pure logic is usable without it.
_GTK_AVAILABLE = False
_GTK_ERROR: str | None = None

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, GObject, Gtk, Pango

    _GTK_AVAILABLE = True
except (ImportError, ValueError) as exc:
    _GTK_ERROR = (
        "GTK4 and PyGObject are required for the verification GUI.\n"
        "Install them with:\n"
        "  sudo apt install python3-gi gir1.2-gtk-4.0\n"
        f"\nUnderlying error: {exc}"
    )


def _require_gtk() -> None:
    """Raise RuntimeError if GTK4 is not available."""
    if not _GTK_AVAILABLE:
        raise RuntimeError(_GTK_ERROR)


# ---------------------------------------------------------------------------
# Formatting helpers (pure Python, no GTK dependency)
# ---------------------------------------------------------------------------

def format_amount_swedish(amount: Decimal) -> str:
    """Format a Decimal amount with Swedish decimal comma notation.

    Examples:
        Decimal("-125.00") -> "-125,00"
        Decimal("10000.00") -> "10 000,00"

    Args:
        amount: The monetary amount to format.

    Returns:
        String with comma as decimal separator and space as thousands separator.
    """
    quantized = amount.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    abs_val = abs(quantized)
    integer_part = int(abs_val)
    decimal_part = abs_val - integer_part

    # Format integer part with space as thousands separator
    int_str = f"{integer_part:,}".replace(",", " ")
    dec_str = f"{decimal_part:.2f}"[1:]  # ".XX"
    dec_str = dec_str.replace(".", ",")

    return f"{sign}{int_str}{dec_str}"


def matches_account_filter(code: int, name: str, search_text: str) -> bool:
    """Check if an account matches the search filter text.

    Matches against both account number and account name (case-insensitive).

    Args:
        code: The account number.
        name: The account name.
        search_text: The text to filter by.

    Returns:
        True if the account matches the filter.
    """
    if not search_text:
        return True
    lower_search = search_text.lower()
    return (
        lower_search in str(code)
        or lower_search in name.lower()
    )


def categorization_count(
    suggestions: list[CategorizationSuggestion],
) -> tuple[int, int]:
    """Count categorized and uncategorized suggestions.

    Args:
        suggestions: List of categorization suggestions.

    Returns:
        Tuple of (categorized_count, uncategorized_count).
    """
    categorized = sum(1 for s in suggestions if s.confidence != "none")
    return categorized, len(suggestions) - categorized


# ---------------------------------------------------------------------------
# GTK-dependent code below — only defined when GTK4 is available
# ---------------------------------------------------------------------------

if _GTK_AVAILABLE:

    class TransactionRow(GObject.Object):
        """GObject wrapper around a CategorizationSuggestion for Gio.ListStore.

        Exposes observable properties so GTK4 widgets can bind to individual
        transaction fields. The ``konto`` and ``moms`` properties are mutable —
        updated when the user selects a different account.
        """

        __gtype_name__ = "TransactionRow"

        def __init__(
            self,
            suggestion: CategorizationSuggestion,
        ) -> None:
            super().__init__()
            self._suggestion = suggestion
            txn = suggestion.transaction
            self._datum = txn.booking_date.isoformat()
            self._text = txn.text
            self._belopp = txn.amount
            self._saldo = txn.balance
            self._konto = suggestion.debit_account if suggestion.confidence != "none" else 0
            self._konto_name = ""
            self._moms = suggestion.vat_rate
            self._is_categorized = suggestion.confidence != "none"
            self._original_confidence = suggestion.confidence
            self._rule_id = suggestion.rule_id
            self._verification_number = txn.verification_number

        # --- Read-only properties ---

        @GObject.Property(type=str)
        def datum(self) -> str:
            return self._datum

        @GObject.Property(type=str)
        def text(self) -> str:
            return self._text

        @GObject.Property(type=str)
        def belopp_display(self) -> str:
            """Amount formatted with Swedish decimal comma notation."""
            return format_amount_swedish(self._belopp)

        @GObject.Property(type=str)
        def saldo_display(self) -> str:
            """Balance formatted with Swedish decimal comma notation."""
            return format_amount_swedish(self._saldo)

        # --- Mutable properties ---

        @GObject.Property(type=int)
        def konto(self) -> int:
            return self._konto

        @konto.setter
        def konto(self, value: int) -> None:
            if self._konto != value:
                self._konto = value
                self._is_categorized = value != 0
                self.notify("konto")
                self.notify("is-categorized")
                self.notify("konto-display")

        @GObject.Property(type=str)
        def konto_name(self) -> str:
            return self._konto_name

        @konto_name.setter
        def konto_name(self, value: str) -> None:
            self._konto_name = value

        @GObject.Property(type=str)
        def konto_display(self) -> str:
            """Konto column display: filled square + number or question mark."""
            if self._is_categorized:
                return f"\u25a0 {self._konto}"
            return "? ----"

        @GObject.Property(type=str)
        def moms_display(self) -> str:
            """VAT rate formatted as percentage string."""
            pct = int(self._moms * 100)
            return f"{pct}%"

        @GObject.Property(type=bool, default=False)
        def is_categorized(self) -> bool:
            return self._is_categorized

        # --- Data access for save flow ---

        @property
        def transaction(self) -> BankTransaction:
            return self._suggestion.transaction

        @property
        def original_suggestion(self) -> CategorizationSuggestion:
            return self._suggestion

        @property
        def debit_account(self) -> int:
            return self._konto

        @property
        def credit_account(self) -> int:
            return self._suggestion.credit_account

        @property
        def vat_rate(self) -> Decimal:
            return self._moms

        @property
        def vat_account(self) -> int | None:
            return self._suggestion.vat_account

        @property
        def rule_id(self) -> int | None:
            return self._rule_id

        @property
        def verification_number(self) -> str:
            return self._verification_number

        def set_account(
            self, account_code: int, vat_rate: Decimal, vat_account: int | None
        ) -> None:
            """Update the account assignment for this row.

            Args:
                account_code: BAS account number to assign.
                vat_rate: The VAT rate for this account.
                vat_account: The VAT account, or None for 0% VAT.
            """
            self._konto = account_code
            self._moms = vat_rate
            self._is_categorized = account_code != 0
            self._suggestion = CategorizationSuggestion(
                transaction=self._suggestion.transaction,
                debit_account=account_code,
                credit_account=self._suggestion.credit_account,
                vat_rate=vat_rate,
                vat_account=vat_account,
                confidence="pattern" if self._is_categorized else "none",
                rule_id=self._rule_id,
            )
            self.notify("konto")
            self.notify("is-categorized")
            self.notify("konto-display")
            self.notify("moms-display")

        def to_journal_entry(self) -> JournalEntry:
            """Convert this row into a balanced JournalEntry.

            Returns:
                A balanced JournalEntry ready for writing to GnuCash.

            Raises:
                ValueError: If the row is not categorized.
            """
            if not self._is_categorized:
                raise ValueError(
                    f"Cannot convert uncategorized row: {self._text}"
                )
            return build_journal_entry(
                verification_number=self._verification_number,
                booking_date=self.transaction.booking_date,
                description=self._text,
                amount=self._belopp,
                debit_account=self._konto,
                credit_account=self.credit_account,
                vat_rate=self._moms,
                vat_account=self.vat_account,
            )

    class AccountItem(GObject.Object):
        """A BAS 2023 account entry for use in the account selector list."""

        __gtype_name__ = "AccountItem"

        def __init__(
            self, code: int, name: str, vat_rate: Decimal = Decimal("0.00")
        ) -> None:
            super().__init__()
            self._code = code
            self._name = name
            self._vat_rate = vat_rate

        @GObject.Property(type=int)
        def code(self) -> int:
            return self._code

        @GObject.Property(type=str)
        def name(self) -> str:
            return self._name

        @GObject.Property(type=str)
        def display_text(self) -> str:
            return f"{self._code} - {self._name}"

        @property
        def vat_rate(self) -> Decimal:
            return self._vat_rate

    # Default VAT rates for common BAS 2023 account ranges.
    # Keys are account code prefixes; values are the VAT rate as Decimal.
    _DEFAULT_VAT_RATES: dict[str, Decimal] = {
        "3010": Decimal("0.25"),   # Försäljning tjänster 25%
        "3011": Decimal("0.12"),   # Försäljning tjänster 12%
        "3012": Decimal("0.06"),   # Försäljning tjänster 6%
        "6212": Decimal("0.25"),   # Programvarulicenser
        "6540": Decimal("0.25"),   # IT-tjänster
    }

    def _lookup_default_vat_rate(code: int) -> Decimal:
        """Look up the default VAT rate for a BAS account code.

        Checks the account code against known VAT rate mappings. Returns
        Decimal("0.00") if no specific rate is known.

        Args:
            code: The BAS account number.

        Returns:
            The VAT rate as a Decimal fraction.
        """
        code_str = str(code)
        if code_str in _DEFAULT_VAT_RATES:
            return _DEFAULT_VAT_RATES[code_str]
        return Decimal("0.00")

    def load_accounts_from_gnucash(
        gnucash_book_path: str,
        vat_rates: dict[int, Decimal] | None = None,
    ) -> list[AccountItem]:
        """Load BAS 2023 accounts from a GnuCash book as AccountItem objects.

        Reads account code and name pairs from the GnuCash book and wraps
        them in AccountItem objects for the account selector. Only accounts
        with a non-empty numeric code are included.

        VAT rates are assigned from the ``vat_rates`` mapping if provided,
        otherwise from built-in defaults for common BAS accounts.

        Args:
            gnucash_book_path: Path to the GnuCash SQLite book file.
            vat_rates: Optional mapping of account code to VAT rate. When
                provided, overrides built-in defaults.

        Returns:
            List of AccountItem objects sorted by account code.

        Raises:
            GnuCashError: If the book cannot be opened.
        """
        from pathlib import Path

        book_path = Path(gnucash_book_path)
        if not book_path.exists():
            raise GnuCashError(f"GnuCash book not found: {book_path}")

        try:
            import piecash

            with piecash.open_book(str(book_path), readonly=True) as book:
                items: list[AccountItem] = []
                for account in book.accounts:
                    if account.code and account.code.strip():
                        try:
                            code = int(account.code.strip())
                        except ValueError:
                            continue
                        if vat_rates and code in vat_rates:
                            rate = vat_rates[code]
                        else:
                            rate = _lookup_default_vat_rate(code)
                        items.append(AccountItem(
                            code=code,
                            name=account.name,
                            vat_rate=rate,
                        ))
                items.sort(key=lambda a: a.code)
                return items
        except Exception as exc:
            if isinstance(exc, GnuCashError):
                raise
            raise GnuCashError(
                f"Failed to read accounts from GnuCash: {exc}"
            ) from exc

    def count_uncategorized(store: Gio.ListStore) -> int:
        """Count rows in the store that are not yet categorized.

        Args:
            store: The list store containing TransactionRow items.

        Returns:
            Number of uncategorized rows.
        """
        count = 0
        for i in range(store.get_n_items()):
            row = store.get_item(i)
            if not row.is_categorized:
                count += 1
        return count

    # --- CSS styling ---

    _APP_CSS = b"""
    .uncategorized-row {
        background-color: rgba(255, 200, 200, 0.3);
    }
    .amount-column {
        font-family: monospace;
    }
    """

    class VerificationWindow(Gtk.ApplicationWindow):
        """Main application window for transaction verification.

        Displays a table of imported transactions with their categorization
        status, provides an account selector for editing, and a save button
        that commits confirmed categorizations to GnuCash.
        """

        def __init__(
            self,
            app: Gtk.Application,
            suggestions: list[CategorizationSuggestion],
            accounts: list[AccountItem],
            new_count: int = 0,
            duplicate_count: int = 0,
            on_save: Callable[[list[JournalEntry]], None] | None = None,
            on_save_rules: Callable[[list[TransactionRow]], None] | None = None,
        ) -> None:
            super().__init__(
                application=app,
                title="Bokföring - Import & Kategorisering",
            )
            self.set_default_size(1000, 700)

            self._on_save = on_save
            self._on_save_rules = on_save_rules
            self._new_count = new_count
            self._duplicate_count = duplicate_count

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(_APP_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Build account list store
            self._account_store = Gio.ListStore(item_type=AccountItem)
            for acct in accounts:
                self._account_store.append(acct)

            # Build transaction model
            self._store = Gio.ListStore(item_type=TransactionRow)
            for suggestion in suggestions:
                self._store.append(TransactionRow(suggestion))

            # Main layout
            main_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self.set_child(main_box)

            # Header bar
            header = Gtk.HeaderBar()
            self.set_titlebar(header)

            # Import summary bar
            self._import_label = Gtk.Label()
            self._import_label.set_margin_start(12)
            self._import_label.set_margin_end(12)
            self._import_label.set_margin_top(8)
            self._import_label.set_margin_bottom(4)
            self._import_label.set_halign(Gtk.Align.START)
            self._update_import_summary()
            main_box.append(self._import_label)

            # Scrolled window with ColumnView
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            scrolled.set_hexpand(True)
            main_box.append(scrolled)

            self._build_column_view(scrolled)

            # Status bar
            status_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            status_box.set_margin_start(12)
            status_box.set_margin_end(12)
            status_box.set_margin_top(8)
            status_box.set_margin_bottom(8)

            self._status_label = Gtk.Label()
            self._status_label.set_halign(Gtk.Align.START)
            self._status_label.set_hexpand(True)
            status_box.append(self._status_label)

            # Cancel button
            cancel_button = Gtk.Button(label="Avbryt")
            cancel_button.connect("clicked", self._on_cancel_clicked)
            status_box.append(cancel_button)

            # Save button
            self._save_button = Gtk.Button(label="Spara till GnuCash")
            self._save_button.add_css_class("suggested-action")
            self._save_button.connect("clicked", self._on_save_clicked)
            status_box.append(self._save_button)

            main_box.append(status_box)

            # Initial status update
            self._update_categorization_status()

        def _build_column_view(
            self, scrolled: Gtk.ScrolledWindow
        ) -> None:
            """Build the ColumnView with all transaction columns."""
            selection = Gtk.SingleSelection(model=self._store)
            self._column_view = Gtk.ColumnView(model=selection)
            self._column_view.set_show_column_separators(True)
            self._column_view.set_show_row_separators(True)
            scrolled.set_child(self._column_view)

            self._add_column("Datum", self._setup_label, self._bind_datum, 100)
            self._add_column("Text", self._setup_text, self._bind_text, 300)
            self._add_column(
                "Belopp", self._setup_amount, self._bind_belopp, 100
            )
            self._add_column(
                "Konto", self._setup_konto, self._bind_konto, 120,
                unbind_fn=self._unbind_konto,
            )
            self._add_column("Moms", self._setup_center, self._bind_moms, 60)
            self._add_column(
                "Saldo", self._setup_amount, self._bind_saldo, 120
            )

        def _add_column(
            self,
            title: str,
            setup_fn: Callable,
            bind_fn: Callable,
            fixed_width: int,
            unbind_fn: Callable | None = None,
        ) -> None:
            """Add a column with a SignalListItemFactory."""
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", setup_fn)
            factory.connect("bind", bind_fn)
            if unbind_fn is not None:
                factory.connect("unbind", unbind_fn)
            column = Gtk.ColumnViewColumn(title=title, factory=factory)
            column.set_fixed_width(fixed_width)
            self._column_view.append_column(column)

        # --- Factory setup helpers ---

        def _setup_label(self, factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            list_item.set_child(label)

        def _setup_text(self, factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            list_item.set_child(label)

        def _setup_amount(self, factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.END)
            label.add_css_class("amount-column")
            list_item.set_child(label)

        def _setup_center(self, factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.CENTER)
            list_item.set_child(label)

        def _setup_konto(self, factory, list_item):
            button = Gtk.Button()
            button.set_halign(Gtk.Align.START)
            list_item.set_child(button)

        # --- Factory bind methods ---

        def _bind_datum(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            label: Gtk.Label = list_item.get_child()
            label.set_text(row.datum)
            self._apply_row_styling(label, row)

        def _bind_text(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            label: Gtk.Label = list_item.get_child()
            label.set_text(row.text)
            self._apply_row_styling(label, row)

        def _bind_belopp(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            label: Gtk.Label = list_item.get_child()
            label.set_text(row.belopp_display)
            self._apply_row_styling(label, row)

        def _bind_konto(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            button: Gtk.Button = list_item.get_child()
            button.set_label(row.konto_display)
            # Disconnect any previous handler to prevent stacking on recycled items
            if hasattr(list_item, "_konto_handler_id") and list_item._konto_handler_id:
                button.disconnect(list_item._konto_handler_id)
            list_item._konto_handler_id = button.connect(
                "clicked", self._on_konto_clicked, row
            )
            self._apply_row_styling(button, row)

        def _unbind_konto(self, factory, list_item):
            """Disconnect the konto button signal handler on unbind."""
            button: Gtk.Button = list_item.get_child()
            if hasattr(list_item, "_konto_handler_id") and list_item._konto_handler_id:
                button.disconnect(list_item._konto_handler_id)
                list_item._konto_handler_id = None

        def _bind_moms(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            label: Gtk.Label = list_item.get_child()
            label.set_text(row.moms_display)
            self._apply_row_styling(label, row)

        def _bind_saldo(self, factory, list_item):
            row: TransactionRow = list_item.get_item()
            label: Gtk.Label = list_item.get_child()
            label.set_text(row.saldo_display)
            self._apply_row_styling(label, row)

        # --- Row styling ---

        def _apply_row_styling(self, widget, row: TransactionRow) -> None:
            """Apply uncategorized CSS class based on row state."""
            if not row.is_categorized:
                widget.add_css_class("uncategorized-row")
            else:
                widget.remove_css_class("uncategorized-row")

        # --- Account selector popover ---

        def _on_konto_clicked(self, button, row: TransactionRow) -> None:
            """Show the account selector popover."""
            popover = Gtk.Popover()
            popover.set_parent(button)

            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(8)
            box.set_margin_bottom(8)

            search_entry = Gtk.SearchEntry()
            search_entry.set_placeholder_text("Sök konto...")
            box.append(search_entry)

            filter_model = Gtk.FilterListModel(model=self._account_store)
            custom_filter = Gtk.CustomFilter.new(
                self._account_filter_func, search_entry
            )
            filter_model.set_filter(custom_filter)

            selection = Gtk.SingleSelection(model=filter_model)

            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._setup_account_item)
            factory.connect("bind", self._bind_account_item)

            list_view = Gtk.ListView(model=selection, factory=factory)
            list_view.set_size_request(300, 300)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_child(list_view)
            scrolled.set_vexpand(True)
            scrolled.set_min_content_height(300)
            box.append(scrolled)

            popover.set_child(box)

            search_entry.connect(
                "search-changed",
                self._on_account_search_changed,
                custom_filter,
            )
            list_view.connect(
                "activate",
                self._on_account_selected,
                selection,
                row,
                popover,
            )

            popover.popup()
            search_entry.grab_focus()

        def _account_filter_func(self, item, search_entry) -> bool:
            search_text = search_entry.get_text()
            return matches_account_filter(item.code, item.name, search_text)

        def _on_account_search_changed(self, search_entry, custom_filter):
            custom_filter.changed(Gtk.FilterChange.DIFFERENT)

        def _setup_account_item(self, factory, list_item):
            label = Gtk.Label()
            label.set_halign(Gtk.Align.START)
            list_item.set_child(label)

        def _bind_account_item(self, factory, list_item):
            item = list_item.get_item()
            label = list_item.get_child()
            label.set_text(item.display_text)

        def _on_account_selected(
            self, list_view, position, selection, row, popover
        ):
            """Handle account selection from the popover."""
            item = selection.get_selected_item()
            if item is None:
                return

            from bookkeeping.categorizer import resolve_vat_account

            vat_account = resolve_vat_account(
                item.vat_rate, row.transaction.amount
            )
            row.set_account(item.code, item.vat_rate, vat_account)
            popover.popdown()
            self._update_categorization_status()

            # Force column view to rebind
            for i in range(self._store.get_n_items()):
                if self._store.get_item(i) is row:
                    self._store.items_changed(i, 1, 1)
                    break

        # --- Status updates ---

        def _update_import_summary(self) -> None:
            """Update the import summary label."""
            parts = []
            if self._new_count:
                parts.append(f"{self._new_count} nya transaktioner")
            if self._duplicate_count:
                parts.append(
                    f"{self._duplicate_count} dubletter borttagna"
                )
            self._import_label.set_text(
                ", ".join(parts) if parts else ""
            )

        def _update_categorization_status(self) -> None:
            """Update the status bar and save button."""
            total = self._store.get_n_items()
            uncategorized = count_uncategorized(self._store)
            categorized = total - uncategorized

            self._status_label.set_text(
                f"{total} transaktioner, {categorized} kategoriserade, "
                f"{uncategorized} kvar"
            )
            self._save_button.set_sensitive(uncategorized == 0)

        # --- Action handlers ---

        def _on_cancel_clicked(self, button) -> None:
            self.close()

        def _on_save_clicked(self, button) -> None:
            """Convert all rows to journal entries and trigger save."""
            entries: list[JournalEntry] = []
            rows: list[TransactionRow] = []

            for i in range(self._store.get_n_items()):
                row = self._store.get_item(i)
                entries.append(row.to_journal_entry())
                rows.append(row)

            try:
                if self._on_save:
                    self._on_save(entries)
                if self._on_save_rules:
                    self._on_save_rules(rows)
                self._show_success_dialog(len(entries))
            except (GnuCashError, RulesDBError) as exc:
                self._show_error_dialog(str(exc))

        def _show_success_dialog(self, count: int) -> None:
            dialog = Gtk.AlertDialog()
            dialog.set_message(
                f"{count} transaktioner sparade till GnuCash."
            )
            dialog.set_detail(
                "Alla transaktioner har importerats och regler "
                "har uppdaterats."
            )
            dialog.set_buttons(["OK"])
            dialog.choose(self, None, self._on_success_response)

        def _on_success_response(self, dialog, result) -> None:
            try:
                dialog.choose_finish(result)
            except GLib.Error:
                pass
            self.close()

        def _show_error_dialog(self, message: str) -> None:
            dialog = Gtk.AlertDialog()
            dialog.set_message("Import misslyckades")
            dialog.set_detail(message)
            dialog.set_buttons(["OK"])
            dialog.choose(self, None, self._on_error_response)

        def _on_error_response(self, dialog, result) -> None:
            """Finish the error dialog interaction."""
            try:
                dialog.choose_finish(result)
            except GLib.Error:
                pass

    class BokforingApp(Gtk.Application):
        """GTK4 application for transaction verification and categorization.

        Receives pre-processed data (suggestions, accounts, counts) and
        displays a verification window. The application does not perform
        CSV parsing or duplicate detection — those happen upstream.
        """

        def __init__(self) -> None:
            super().__init__(
                application_id="se.bokforing.verification",
                flags=Gio.ApplicationFlags.FLAGS_NONE,
            )
            self._suggestions: list[CategorizationSuggestion] = []
            self._accounts: list[AccountItem] = []
            self._new_count = 0
            self._duplicate_count = 0
            self._on_save: Callable[
                [list[JournalEntry]], None
            ] | None = None
            self._on_save_rules: Callable[
                [list[TransactionRow]], None
            ] | None = None

        def configure(
            self,
            suggestions: list[CategorizationSuggestion],
            accounts: list[AccountItem],
            new_count: int = 0,
            duplicate_count: int = 0,
            on_save: Callable[
                [list[JournalEntry]], None
            ] | None = None,
            on_save_rules: Callable[
                [list[TransactionRow]], None
            ] | None = None,
        ) -> None:
            """Configure the application with data before running.

            Args:
                suggestions: Transaction categorization suggestions.
                accounts: BAS 2023 accounts for the selector.
                new_count: Number of new transactions.
                duplicate_count: Number of duplicates skipped.
                on_save: Callback with journal entries on save.
                on_save_rules: Callback with rows for rule updates.
            """
            self._suggestions = suggestions
            self._accounts = accounts
            self._new_count = new_count
            self._duplicate_count = duplicate_count
            self._on_save = on_save
            self._on_save_rules = on_save_rules

        def do_activate(self) -> None:
            """Create and present the main application window."""
            window = VerificationWindow(
                app=self,
                suggestions=self._suggestions,
                accounts=self._accounts,
                new_count=self._new_count,
                duplicate_count=self._duplicate_count,
                on_save=self._on_save,
                on_save_rules=self._on_save_rules,
            )
            window.present()
