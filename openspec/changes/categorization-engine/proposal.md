## Why

Transactions imported from bank CSV need BAS 2023 account mapping suggestions based on stored categorization rules. Without this engine, every transaction would require manual categorization in the GUI, defeating the goal of 90%+ auto-suggestion accuracy for recurring transactions. The categorizer bridges the gap between raw bank data and GnuCash journal entries by matching transaction text against learned patterns.

## What Changes

- Implement `bookkeeping/categorizer.py` with:
  - `suggest_categorization(transaction: BankTransaction, rules_db: RulesDatabase) -> CategorizationSuggestion | None`
  - `save_rule(rules_db: RulesDatabase, pattern: str, debit_account: int, credit_account: int, vat_rate: Decimal) -> None`
- Pattern matching logic:
  1. Exact match on full transaction `Text` field (highest priority, returns "exact" confidence)
  2. Contains match on normalized text (lowercase, stripped date suffixes like `/26-01-23`) (returns "pattern" confidence)
  3. If multiple contains matches, use the rule with the most recent `last_used` date
  4. No match returns `None`
- Text normalization: lowercase the text and strip trailing date suffixes (e.g., `/26-01-23`)
- Suggestions include VAT split info generated via `VATSplit` from `bookkeeping/vat.py`
- Never auto-commits -- always returns suggestions for user confirmation

## Capabilities

### New Capabilities
- `transaction-categorization`: Rule-based transaction categorization with exact/pattern matching, text normalization, confidence levels, and VAT split generation

### Modified Capabilities

## Impact

- **Code**: New module `bookkeeping/categorizer.py` and test file `tests/test_categorizer.py`
- **Dependencies**: Depends on `bookkeeping/models.py` (BankTransaction, CategorizationSuggestion, Rule), `bookkeeping/rules_db.py` (RulesDatabase), and `bookkeeping/vat.py` (apply_vat_split, VATSplit)
- **Data**: Consumes BankTransaction objects and RulesDatabase, produces CategorizationSuggestion objects or None
