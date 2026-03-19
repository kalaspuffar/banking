## ADDED Requirements

### Requirement: Suggest categorization via exact match
The system SHALL provide a function `suggest_categorization(transaction: BankTransaction, rules_db: RulesDatabase) -> CategorizationSuggestion | None` that first attempts an exact match on the transaction's full `text` field against stored rules.

#### Scenario: Exact match returns "exact" confidence
- **WHEN** `suggest_categorization` is called with a transaction whose `text` exactly matches a rule's pattern with match_type "exact"
- **THEN** it returns a CategorizationSuggestion with `confidence = "exact"` and the matched rule's account mappings and VAT rate

### Requirement: Suggest categorization via contains match
When no exact match is found, the system SHALL attempt a contains match using the normalized transaction text against rules with match_type "contains".

#### Scenario: Contains match returns "pattern" confidence
- **WHEN** `suggest_categorization` is called with a transaction whose normalized text contains a rule's pattern
- **AND** no exact match exists
- **THEN** it returns a CategorizationSuggestion with `confidence = "pattern"` and the matched rule's account mappings

### Requirement: Return None when no match
The system SHALL return `None` when no categorization rule matches the transaction text, either exactly or via contains.

#### Scenario: No match returns None
- **WHEN** `suggest_categorization` is called with a transaction whose text does not match any stored rule
- **THEN** it returns `None`

### Requirement: Resolve multiple contains matches by recency
When multiple contains rules match a transaction's normalized text, the system SHALL select the rule with the most recent `last_used` date.

#### Scenario: Multiple contains matches picks most recent last_used
- **WHEN** `suggest_categorization` finds two contains rules matching the normalized text
- **AND** rule A has `last_used = 2026-01-15` and rule B has `last_used = 2026-02-20`
- **THEN** it returns a CategorizationSuggestion based on rule B

### Requirement: Normalize transaction text for matching
The system SHALL normalize transaction text by converting to lowercase and stripping trailing date suffixes matching the pattern `/YY-MM-DD` before performing contains matching.

#### Scenario: Text normalization strips date suffixes
- **WHEN** a transaction has text "Spotify AB/26-01-23"
- **THEN** the normalized text used for contains matching is "spotify ab"

#### Scenario: Text without date suffix normalized to lowercase only
- **WHEN** a transaction has text "BANKAVGIFT"
- **THEN** the normalized text used for contains matching is "bankavgift"

### Requirement: Save categorization rule
The system SHALL provide a function `save_rule(rules_db: RulesDatabase, pattern: str, debit_account: int, credit_account: int, vat_rate: Decimal) -> None` that persists a new categorization rule to the RulesDatabase.

#### Scenario: save_rule persists new rule to RulesDatabase
- **WHEN** `save_rule` is called with pattern "spotify ab", debit_account 6540, credit_account 1930, vat_rate Decimal("0.25")
- **THEN** the rule is saved to the RulesDatabase and can be found by subsequent `suggest_categorization` calls

### Requirement: Include VAT split info in suggestions
The system SHALL include VAT split information in CategorizationSuggestion by calling `apply_vat_split` from `bookkeeping/vat.py` with the transaction amount and the matched rule's VAT rate.

#### Scenario: Suggestion includes VAT split for 25% rate
- **WHEN** a transaction with `belopp = Decimal("-125.00")` matches a rule with `vat_rate = Decimal("0.25")`
- **THEN** the CategorizationSuggestion includes `vat_rate = Decimal("0.25")` and the appropriate `vat_account` (e.g., 2640 for input VAT)

#### Scenario: Suggestion with 0% VAT has no VAT account
- **WHEN** a transaction matches a rule with `vat_rate = Decimal("0.00")`
- **THEN** the CategorizationSuggestion has `vat_account = None`
