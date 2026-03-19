"""Rule-based transaction categorization engine.

Matches bank transaction descriptions against stored categorization rules to
suggest BAS 2023 account mappings. Supports two match strategies:

1. **Exact match** — the full transaction text equals a rule's pattern.
2. **Contains match** — the normalized transaction text contains a rule's pattern.

Text normalization strips trailing bank date suffixes (e.g., ``/26-01-23``) and
lowercases the text so that recurring vendor transactions like
"Spotify AB/26-01-23" and "SPOTIFY AB/25-12-15" both match a rule for
"spotify ab".

When multiple contains rules match, the rule with the most recent ``last_used``
date wins. Suggestions include VAT split information from :mod:`bookkeeping.vat`.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from bookkeeping.models import (
    BankTransaction,
    CategorizationSuggestion,
    Rule,
)
from bookkeeping.rules_db import RulesDatabase
from bookkeeping.vat import apply_vat_split

# Trailing date suffix pattern: /YY-MM-DD at end of string
_DATE_SUFFIX_RE = re.compile(r"/\d{2}-\d{2}-\d{2}$")

# VAT account mapping by rate and transaction direction.
# Negative amounts are expenses (ingående moms 2640),
# positive amounts are income (utgående moms 2610).
_VAT_ACCOUNTS: dict[Decimal, dict[str, int]] = {
    Decimal("0.25"): {"expense": 2640, "income": 2610},
    Decimal("0.12"): {"expense": 2640, "income": 2620},
    Decimal("0.06"): {"expense": 2640, "income": 2630},
}


def normalize_text(text: str) -> str:
    """Normalize transaction text for pattern matching.

    Lowercases the text and strips trailing bank date suffixes that match
    the format ``/YY-MM-DD`` (e.g., ``/26-01-23``). This allows transactions
    like "Spotify AB/26-01-23" and "SPOTIFY AB/25-12-15" to match the same
    contains rule for "spotify ab".

    Args:
        text: Raw transaction description from the bank CSV.

    Returns:
        Normalized lowercase text with any trailing date suffix removed.
    """
    normalized = text.lower()
    normalized = _DATE_SUFFIX_RE.sub("", normalized)
    return normalized


def _resolve_vat_account(
    vat_rate: Decimal, amount: Decimal
) -> int | None:
    """Determine the appropriate BAS VAT account for a transaction.

    Args:
        vat_rate: The VAT rate as a decimal fraction (e.g., 0.25).
        amount: The transaction amount (negative = expense, positive = income).

    Returns:
        The BAS VAT account number, or None if the VAT rate is 0%.
    """
    if vat_rate == Decimal("0.00"):
        return None

    rate_accounts = _VAT_ACCOUNTS.get(vat_rate)
    if rate_accounts is None:
        return None

    direction = "expense" if amount < 0 else "income"
    return rate_accounts[direction]


def suggest_categorization(
    transaction: BankTransaction,
    rules_db: RulesDatabase,
) -> CategorizationSuggestion | None:
    """Suggest a BAS 2023 account mapping for a bank transaction.

    Searches stored categorization rules in priority order:
    1. Exact match on the full transaction text.
    2. Contains match on the normalized text (lowercase, date-suffix-stripped).
    3. If multiple contains rules match, picks the most recently used one.

    Returns None if no rule matches, leaving the transaction for manual
    categorization in the GUI.

    Args:
        transaction: The bank transaction to categorize.
        rules_db: The rules database to search.

    Returns:
        A CategorizationSuggestion with account mappings, VAT info, and
        confidence level, or None if no rule matches.
    """
    all_rules = rules_db.list_rules()

    # Priority 1: exact match on full transaction text
    exact_matches = [
        rule for rule in all_rules
        if rule.match_type == "exact" and rule.pattern == transaction.text
    ]
    if exact_matches:
        best_rule = max(exact_matches, key=lambda r: r.last_used)
        return _build_suggestion(transaction, best_rule, confidence="exact")

    # Priority 2: contains match on normalized text
    normalized = normalize_text(transaction.text)
    contains_matches = [
        rule for rule in all_rules
        if rule.match_type == "contains" and rule.pattern in normalized
    ]
    if contains_matches:
        best_rule = max(contains_matches, key=lambda r: r.last_used)
        return _build_suggestion(transaction, best_rule, confidence="pattern")

    return None


def _build_suggestion(
    transaction: BankTransaction,
    rule: Rule,
    confidence: str,
) -> CategorizationSuggestion:
    """Build a CategorizationSuggestion from a matched rule.

    Calls apply_vat_split to include VAT information and determines the
    appropriate VAT account based on the rate and transaction direction.

    Args:
        transaction: The originating bank transaction.
        rule: The matched categorization rule.
        confidence: The match confidence level ("exact" or "pattern").

    Returns:
        A fully populated CategorizationSuggestion.
    """
    apply_vat_split(transaction.amount, rule.vat_rate)
    vat_account = _resolve_vat_account(rule.vat_rate, transaction.amount)

    return CategorizationSuggestion(
        transaction=transaction,
        debit_account=rule.debit_account,
        credit_account=rule.credit_account,
        vat_rate=rule.vat_rate,
        vat_account=vat_account,
        confidence=confidence,
        rule_id=rule.id,
    )


def save_rule(
    rules_db: RulesDatabase,
    pattern: str,
    debit_account: int,
    credit_account: int,
    vat_rate: Decimal,
) -> None:
    """Save a new categorization rule to the rules database.

    Creates a Rule object with match_type "contains" (the default for
    user-created rules, since exact matches are typically auto-generated
    from confirmed transactions) and delegates to rules_db.save_rule().

    The VAT account is determined automatically based on the VAT rate.
    Rules with 0% VAT have no VAT account.

    Args:
        rules_db: The rules database to save into.
        pattern: Text pattern to match against transaction descriptions.
            Should be lowercase for contains matching.
        debit_account: BAS account number to debit.
        credit_account: BAS account number to credit.
        vat_rate: VAT rate as a decimal fraction (e.g., Decimal("0.25")).
    """
    # For save_rule, we use a negative amount sentinel to determine the
    # VAT account direction. Since debit_account is the expense/asset
    # account and credit_account is the bank, a non-bank debit implies
    # an expense (negative amount direction).
    # Heuristic: if debit_account is not 1930 (bank), it's an expense.
    is_expense = debit_account != 1930
    vat_account = _resolve_vat_account(
        vat_rate,
        Decimal("-1") if is_expense else Decimal("1"),
    )

    rule = Rule(
        id=None,
        pattern=pattern,
        match_type="contains",
        debit_account=debit_account,
        credit_account=credit_account,
        vat_rate=vat_rate,
        vat_account=vat_account,
        last_used=date.today(),
        use_count=1,
    )
    rules_db.save_rule(rule)
