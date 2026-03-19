## 1. Application Shell

- [ ] 1.1 Create `bookkeeping/gtk_app.py` with a `Gtk.Application` subclass (`BokforingApp`) that handles `gi.require_version('Gtk', '4.0')` with a graceful error message if GTK4/PyGObject is not installed
- [ ] 1.2 Implement the main application window (`Gtk.ApplicationWindow`) with header bar titled "Bokforing - Import & Kategorisering", a scrolled main area, status bar, and action button row

## 2. Transaction Table (ColumnView)

- [ ] 2.1 Define a `TransactionRow` GObject subclass to serve as the model item for `Gio.ListStore`, wrapping `CategorizationSuggestion` with observable properties (datum, text, belopp, konto, moms, saldo, is_categorized)
- [ ] 2.2 Implement `Gtk.ColumnView` with columns: Datum, Text, Belopp, Konto, Moms, Saldo — each with a `Gtk.SignalListItemFactory` that binds to the corresponding `TransactionRow` property
- [ ] 2.3 Format Belopp column with Swedish decimal comma notation (e.g., `-125,00`) and right-alignment
- [ ] 2.4 Display visual indicators in the Konto column: filled square + account number for categorized rows, question mark + "----" for uncategorized rows

## 3. Account Selector

- [ ] 3.1 Load BAS 2023 accounts from the GnuCash book (account code + name pairs) into a `Gio.ListStore`
- [ ] 3.2 Implement a `Gtk.Popover` containing a `Gtk.SearchEntry` and a `Gtk.ListView` for filtered account selection, triggered when the user clicks a Konto cell
- [ ] 3.3 Implement filter logic: match typed text against both account number and account name (case-insensitive)
- [ ] 3.4 On account selection, update the `TransactionRow` konto property and refresh the visual indicator and categorization count

## 4. Categorization Status and Highlighting

- [ ] 4.1 Apply distinct CSS styling (background color) to uncategorized rows in the ColumnView
- [ ] 4.2 Implement a reactive categorization counter that updates the status bar whenever a row's categorization status changes
- [ ] 4.3 Enable/disable the "Spara till GnuCash" button based on whether all rows are categorized (bind to the counter reaching zero uncategorized)

## 5. Save Flow

- [ ] 5.1 Implement the save action: convert all `TransactionRow` objects to `JournalEntry` objects with correct splits (including VAT splits)
- [ ] 5.2 Call `gnucash_writer.write_transactions()` with the generated journal entries; handle success and error cases
- [ ] 5.3 On successful write, iterate through rows and call `rules_db.save_rule()` for each transaction where the user confirmed or changed the categorization
- [ ] 5.4 Show a success dialog with import count, or an error dialog with the failure message

## 6. Status Bar and Import Summary

- [ ] 6.1 Implement the import summary display showing counts of new transactions and duplicates skipped (passed in from the CLI pipeline)
- [ ] 6.2 Implement the categorization progress display: "N transaktioner, M kategoriserade, K kvar" — updated reactively as the user works

## 7. Tests

- [ ] 7.1 Create `tests/test_gtk_app.py` with unit tests for: `TransactionRow` model creation and property access, journal entry conversion logic, categorization counting logic
- [ ] 7.2 Add tests for account filter logic (matching by number, matching by name, case-insensitive filtering)
- [ ] 7.3 Add a test verifying that the save button enable/disable logic correctly reflects categorization state
