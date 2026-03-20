"""Rule-based transaction categorization engine.

Matches bank transaction descriptions against stored categorization rules to
suggest BAS 2023 account mappings. Supports two match strategies:

1. **Exact match** — the full transaction text equals a rule's pattern.
2. **Contains match** — the normalized transaction text contains a rule's pattern.

Text normalization strips trailing bank date suffixes (e.g., ``/26-01-23``) and
lowercases the text so that recurring vendor transactions like
"Spotify AB/26-01-23" and "SPOTIFY AB/25-12-15" both match a rule for
"spotify ab".

When multiple rules match, ``RulesDatabase.find_rule()`` resolves ties by
``last_used`` date (most recent wins). Suggestions include VAT account
information determined from the rate and transaction direction.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from bookkeeping.models import (
    BankTransaction,
    CategorizationSuggestion,
    Confidence,
    Rule,
    TextAlias,
)
from bookkeeping.rules_db import RulesDatabase

# Trailing date suffix pattern: /YY-MM-DD at end of string
_DATE_SUFFIX_RE = re.compile(r"/\d{2}-\d{2}-\d{2}$")

# VAT account mapping by rate and transaction direction.
# Negative amounts are expenses → input VAT (ingående moms, 2640),
# positive amounts are income → output VAT (utgående moms, 2610).
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


def resolve_vat_account(
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
        supported = ", ".join(str(r) for r in sorted(_VAT_ACCOUNTS))
        raise ValueError(
            f"Unsupported non-zero VAT rate: {vat_rate}. "
            f"Supported non-zero rates are: {supported}"
        )

    direction = "expense" if amount < 0 else "income"
    return rate_accounts[direction]


def _try_match(
    transaction: BankTransaction,
    text: str,
    rules_db: RulesDatabase,
) -> CategorizationSuggestion | None:
    """Attempt to match a text string against the rules database.

    Tries an exact match first, then a contains match on both the raw and
    normalized (date-suffix-stripped) versions of the text.

    Args:
        transaction: The originating bank transaction.
        text: The text to match against rule patterns.
        rules_db: The rules database to search.

    Returns:
        A CategorizationSuggestion if a rule matches, otherwise None.
    """
    rule = rules_db.find_rule(text)
    if rule and rule.match_type == "exact":
        return _build_suggestion(transaction, rule, confidence="exact")

    # Try normalized text (date-suffix-stripped, lowercased)
    normalized = normalize_text(text)
    if normalized != text:
        rule_from_normalized = rules_db.find_rule(normalized)
        if rule_from_normalized:
            return _build_suggestion(
                transaction, rule_from_normalized, confidence="pattern"
            )

    # The first find_rule call may have returned a contains match
    if rule:
        return _build_suggestion(transaction, rule, confidence="pattern")

    return None


def suggest_categorization(
    transaction: BankTransaction,
    rules_db: RulesDatabase,
) -> CategorizationSuggestion | None:
    """Suggest a BAS 2023 account mapping for a bank transaction.

    Delegates matching to ``RulesDatabase.find_rule()``, which performs the
    exact-then-contains priority search in SQL. The categorizer normalizes
    the transaction text (stripping date suffixes) and passes the normalized
    text to ``find_rule()`` for the contains search.

    Returns None if no rule matches, leaving the transaction for manual
    categorization in the GUI.

    Note:
        This function does **not** call ``rules_db.update_last_used()``.
        The caller (typically the GUI confirmation step) is responsible for
        updating ``last_used`` after the user accepts a suggestion.

    Args:
        transaction: The bank transaction to categorize.
        rules_db: The rules database to search.

    Returns:
        A CategorizationSuggestion with account mappings, VAT info, and
        confidence level, or None if no rule matches.
    """
    # Try matching against the original bank text first, then fall back
    # to display_text (alias-rewritten) so that rules work regardless of
    # whether they target the raw bank code or the human-readable alias.
    raw_text = transaction.text

    result = _try_match(transaction, raw_text, rules_db)
    if result is not None:
        return result

    # Fall back to display_text when available (alias-rewritten text)
    if transaction.display_text:
        result = _try_match(transaction, transaction.display_text, rules_db)
        if result is not None:
            return result

    return None


def _build_suggestion(
    transaction: BankTransaction,
    rule: Rule,
    confidence: Confidence,
) -> CategorizationSuggestion:
    """Build a CategorizationSuggestion from a matched rule.

    Determines the appropriate VAT account based on the rate and transaction
    direction (expense vs. income). The actual VAT split calculation is
    deferred to the downstream JournalEntry construction step, since the
    suggestion only needs to carry the rate and account — not the split
    amounts.

    Args:
        transaction: The originating bank transaction.
        rule: The matched categorization rule.
        confidence: The match confidence level ("exact" or "pattern").

    Returns:
        A fully populated CategorizationSuggestion.
    """
    vat_account = resolve_vat_account(rule.vat_rate, transaction.amount)

    return CategorizationSuggestion(
        transaction=transaction,
        debit_account=rule.debit_account,
        credit_account=rule.credit_account,
        vat_rate=rule.vat_rate,
        vat_account=vat_account,
        confidence=confidence,
        rule_id=rule.id,
    )


def apply_aliases(text: str, aliases: list[TextAlias]) -> str | None:
    """Find the first matching alias for a transaction text.

    Aliases are expected to be ordered by pattern length descending (longest
    first), so more specific patterns take priority. Matching is
    case-insensitive substring containment.

    Args:
        text: Raw transaction description from the bank CSV.
        aliases: List of TextAlias objects, ordered longest-pattern-first.

    Returns:
        The replacement text from the first matching alias, or None if
        no alias matches.
    """
    text_lower = text.lower()
    for alias in aliases:
        if alias.pattern.lower() in text_lower:
            return alias.replacement
    return None


def save_rule(
    rules_db: RulesDatabase,
    pattern: str,
    debit_account: int,
    credit_account: int,
    vat_rate: Decimal,
    amount: Decimal,
    match_type: MatchType = "contains",
) -> None:
    """Save a new categorization rule to the rules database.

    Creates a Rule object and delegates to rules_db.save_rule(). The default
    match_type is "contains" (for user-created rules), but "exact" can be
    specified for precise text matching.

    The VAT account is determined automatically from the VAT rate and the
    sign of ``amount`` (negative = expense → ingående moms, positive =
    income → utgående moms). Rules with 0% VAT have no VAT account.

    Args:
        rules_db: The rules database to save into.
        pattern: Text pattern to match against transaction descriptions.
            Should be lowercase for contains matching.
        debit_account: BAS account number to debit.
        credit_account: BAS account number to credit.
        vat_rate: VAT rate as a decimal fraction (e.g., Decimal("0.25")).
        amount: A representative transaction amount whose sign determines
            the VAT account direction (negative = expense, positive = income).
        match_type: Either "exact" or "contains" (default).
    """
    vat_account = resolve_vat_account(vat_rate, amount)

    rule = Rule(
        id=None,
        pattern=pattern,
        match_type=match_type,
        debit_account=debit_account,
        credit_account=credit_account,
        vat_rate=vat_rate,
        vat_account=vat_account,
        last_used=date.today(),
        use_count=1,
    )
    rules_db.save_rule(rule)
