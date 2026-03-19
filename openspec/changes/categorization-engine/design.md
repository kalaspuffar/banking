## Context

The categorization engine is the intelligence layer of the import pipeline. After CSV parsing and duplicate detection, each transaction needs a BAS 2023 account mapping suggestion. For a small enskild firma with recurring transactions (subscriptions, bank fees, consulting invoices), rule-based matching can achieve 90%+ auto-suggestion accuracy. The engine must also generate correct VAT split structures for double-entry bookkeeping.

## Goals / Non-Goals

**Goals:**
- Match incoming transactions against stored categorization rules
- Generate CategorizationSuggestion objects with debit/credit accounts, VAT rate, and confidence level
- Handle text normalization to improve matching (date suffix stripping, case folding)
- Include VAT split information in suggestions using VATSplit from vat.py
- Provide a save_rule wrapper for persisting new/updated rules after user confirmation

**Non-Goals:**
- ML-based or fuzzy matching (rule-based only for Phase 1)
- Auto-committing transactions to GnuCash (always returns suggestions)
- Managing the rules database schema (that is rules_db's responsibility)
- Handling the GUI interaction flow (that is gtk_app's responsibility)

## Decisions

### 1. Normalize text by lowercasing and stripping date suffixes
**Rationale**: Bank transaction texts often contain appended dates like `/26-01-23` or `/25-12-15` that vary per occurrence of the same vendor. Stripping these and lowercasing allows "Spotify AB/26-01-23" and "SPOTIFY AB/25-12-15" to match the same "contains" rule for "spotify ab".
**Pattern**: Regex `r'/\d{2}-\d{2}-\d{2}$'` to strip trailing date suffixes.

### 2. Priority order: exact match > contains match > no match
**Rationale**: Exact matches are unambiguous and should always win. Contains matches are useful for recurring vendors whose transaction text varies slightly. If no rule matches, return None so the GUI can highlight the transaction for manual categorization.

### 3. Multiple contains matches resolved by most recent last_used
**Rationale**: The most recently used rule is likely the most relevant. This handles cases where a vendor name appears as a substring of multiple rules -- the one the user confirmed most recently takes precedence.

### 4. Use VATSplit from vat.py for split generation
**Rationale**: VAT calculation logic is already implemented in a dedicated module. The categorizer calls `apply_vat_split(amount, vat_rate)` to populate the suggestion with correct net/VAT amounts, avoiding code duplication and ensuring consistent rounding.

### 5. Confidence levels as strings: "exact", "pattern"
**Rationale**: Simple, descriptive confidence values that the GUI can use to display match quality. "exact" means the full text matched a rule exactly. "pattern" means a normalized contains match was found. No match returns None rather than a suggestion with "none" confidence.

## Risks / Trade-offs

- **[Risk] Overly broad contains patterns match wrong transactions** → Mitigation: exact matches always take priority; users can delete or refine rules via `bookkeeping rules` CLI
- **[Risk] Date suffix regex doesn't cover all bank date formats** → Mitigation: start with observed `/YY-MM-DD` format; extend regex if other formats appear in real data
- **[Trade-off] No fuzzy/ML matching limits accuracy for new vendors** → Acceptable: the GUI handles uncategorized transactions, and rules accumulate over time
