## Context

The bank (likely a Swedish bank) exports transaction history as semicolon-delimited CSV files in UTF-8. The sample file `account.csv` in the repository demonstrates the format. The parser is the entry point for all data flowing into the system and must be robust against malformed input.

## Goals / Non-Goals

**Goals:**
- Parse the exact CSV format exported by the user's bank
- Convert Swedish amount notation to exact Decimal values
- Provide clear error messages with line numbers for malformed input
- Return sorted, validated BankTransaction objects

**Non-Goals:**
- Supporting multiple bank formats (single bank for now)
- Streaming/chunked parsing (files are small, ~200-400 rows/year)
- Automatic encoding detection (assume UTF-8)

## Decisions

### 1. Use Python stdlib `csv` module with `delimiter=';'`
**Rationale**: Standard library, no dependencies. The CSV format is simple enough that no third-party library is needed.
**Alternative considered**: pandas — too heavy for this use case.

### 2. Amount parsing: strip trailing zero from 3-decimal format
**Rationale**: The bank exports amounts like `-100.000` (3 decimal places). This is the Swedish convention where the third decimal is always zero. Parse by converting the string to Decimal directly — the 3-decimal representation is valid Decimal syntax, just with extra precision. Quantize to 2 decimal places.
**Alternative considered**: Regex-based parsing — fragile and unnecessary when Decimal handles it.

### 3. Validate header row strictly
**Rationale**: If the bank changes its export format, the parser should fail loudly rather than silently misinterpreting columns.

## Risks / Trade-offs

- **[Risk] Bank changes CSV format** → Mitigation: Parser is isolated in one module; header validation catches changes immediately
- **[Risk] Encoding issues with Swedish characters (å, ä, ö)** → Mitigation: Explicitly open with UTF-8 encoding; the Text field may contain Swedish characters
