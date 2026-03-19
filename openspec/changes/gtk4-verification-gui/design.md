## Context

This is Phase 2 of the implementation plan. The GTK4 verification GUI sits between the categorization engine (which produces suggestions) and the GnuCash writer (which commits transactions). It is the user's primary point of control — the place where they accept, correct, or assign account mappings before anything is written to the books.

The application receives a list of `CategorizationSuggestion` objects (some with suggested accounts, some without) and presents them in an editable table. The user works through any uncategorized rows, then clicks save to commit everything at once.

## Goals / Non-Goals

**Goals:**
- Single-window GTK4 application displaying all imported transactions in a table
- Transaction table with inline account editing via a searchable account selector
- Clear visual distinction between categorized and uncategorized rows
- Status bar showing categorization progress (e.g., "6 transaktioner, 4 kategoriserade, 2 kvar")
- Save action triggers `gnucash_writer.write_transactions()` and persists new/updated rules via `rules_db`
- Running balance column for reconciliation against the bank's saldo values
- Import summary display (new transactions, duplicates skipped, errors)

**Non-Goals:**
- Multi-window interface (everything in one window)
- Preferences dialog or settings UI (configuration is via CLI `bookkeeping config`)
- Drag-and-drop reordering of transactions
- Direct CSV file opening from the GUI (CSV is passed in from the CLI pipeline)
- Undo/redo within the GUI session
- Dark mode or custom theming

## Decisions

### 1. GTK4 via PyGObject (`gi.repository.Gtk` version 4.0)
**Rationale**: User preference for native Linux toolkit. GTK4 is available in Debian repos (`gir1.2-gtk-4.0`). PyGObject provides Python bindings without needing C compilation.
**Alternative considered**: Qt6/PySide6 — heavier dependency, not the user's preference.

### 2. `Gtk.ColumnView` for the transaction table
**Rationale**: GTK4's `Gtk.ColumnView` is the modern replacement for `Gtk.TreeView`. It supports per-column factories, sorting, and works well with `Gio.ListStore` as the backing model. Each row maps to one `CategorizationSuggestion`.
**Alternative considered**: `Gtk.TreeView` — deprecated in GTK4, still functional but not recommended for new code.

### 3. `Gtk.SearchEntry` + `Gtk.ListView` for account selector
**Rationale**: When the user clicks the Konto column of a row, a popover or inline widget appears with a `Gtk.SearchEntry` at the top and a filtered `Gtk.ListView` showing matching BAS accounts (e.g., "1930 - Foretagskonto"). This provides fast keyboard-driven selection from ~100+ accounts.
**Alternative considered**: `Gtk.DropDown` — lacks search/filter capability for large lists.

### 4. Single-window layout with header bar, table, and action bar
**Rationale**: Keeps the interface simple. The header bar contains the window title. The main area is the transaction `ColumnView` in a scrolled window. The bottom has a status bar (counts) and action buttons ("Spara till GnuCash", "Avbryt").

### 5. Save triggers both GnuCash write and rules update
**Rationale**: When the user clicks save, the application (a) converts all rows to `JournalEntry` objects and calls `gnucash_writer.write_transactions()`, then (b) for any rows where the user accepted or changed a categorization, saves or updates the corresponding rule in `rules_db`. This ensures the system learns from every import session.

## Risks / Trade-offs

- **[Risk] GTK4 not available on older distros** -> Mitigation: Target Debian 12+ / Ubuntu 22.04+ where GTK4 is standard. The CLI `--no-gui` flag provides a fallback.
- **[Risk] PyGObject introspection errors at import time** -> Mitigation: Wrap the `gi.require_version` / import in a try-except with a clear error message telling the user to install `python3-gi` and `gir1.2-gtk-4.0`.
- **[Trade-off] ColumnView complexity** -> ColumnView requires more boilerplate (factories, bindings) than TreeView, but it is the forward-looking GTK4 approach and avoids deprecation warnings.
- **[Trade-off] No undo** -> Simplifies implementation; the user can close without saving to discard all changes.
