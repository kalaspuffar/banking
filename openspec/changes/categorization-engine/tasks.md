## 1. Create Categorizer Module

- [ ] 1.1 Create `bokforing/categorizer.py` with imports for BankTransaction, CategorizationSuggestion, Rule from models, RulesDatabase from rules_db, and apply_vat_split from vat

## 2. Implement Text Normalization

- [ ] 2.1 Implement `normalize_text(text: str) -> str` that lowercases the input and strips trailing date suffixes matching regex `/\d{2}-\d{2}-\d{2}$`
- [ ] 2.2 Handle edge cases: text with no suffix, text that is already lowercase, empty text

## 3. Implement suggest_categorization

- [ ] 3.1 Implement exact match lookup: query rules_db for a rule with match_type "exact" where pattern equals the full transaction text
- [ ] 3.2 Implement contains match lookup: if no exact match, normalize the transaction text and query rules_db for rules with match_type "contains" where the normalized text contains the rule pattern
- [ ] 3.3 Implement multiple match resolution: when multiple contains rules match, select the one with the most recent `last_used` date
- [ ] 3.4 Build CategorizationSuggestion from the matched rule, including calling `apply_vat_split` for VAT info and setting the appropriate `vat_account` based on the VAT rate and transaction direction
- [ ] 3.5 Set confidence to "exact" for exact matches, "pattern" for contains matches; return None when no rule matches

## 4. Implement Confidence Levels

- [ ] 4.1 Ensure "exact" confidence is returned only for exact match_type rule matches
- [ ] 4.2 Ensure "pattern" confidence is returned only for contains match_type rule matches

## 5. Implement save_rule Wrapper

- [ ] 5.1 Implement `save_rule(rules_db, pattern, debit_account, credit_account, vat_rate)` that creates a Rule object and delegates to `rules_db.save_rule()`
- [ ] 5.2 Determine appropriate match_type and vat_account based on the provided parameters

## 6. Tests

- [ ] 6.1 Create `tests/test_categorizer.py` with a mock RulesDatabase
- [ ] 6.2 Test exact match returns CategorizationSuggestion with confidence "exact"
- [ ] 6.3 Test contains match returns CategorizationSuggestion with confidence "pattern"
- [ ] 6.4 Test no match returns None
- [ ] 6.5 Test multiple contains matches picks rule with most recent last_used
- [ ] 6.6 Test text normalization: date suffix stripping, lowercasing
- [ ] 6.7 Test save_rule persists rule via RulesDatabase
- [ ] 6.8 Test VAT split info is included in suggestions (25% and 0% cases)
