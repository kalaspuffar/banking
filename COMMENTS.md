# Code Review Comments

**Branch:** main
**Reviewer:** Claude Code
**Date:** 2026-03-19
**Specification:** SPECIFICATION.md

## Summary

This review covers the full codebase after 3 commits: initial commit, project scaffolding with data models and OpenSpec changes, and dev environment docs. The project is in early scaffolding stage — only `models.py` contains real implementation code; the remaining modules (`cli.py`, `__main__.py`, `__init__.py`) are stubs. The OpenSpec workflow artifacts (proposals, designs, specs, tasks) are comprehensive and well-structured across all planned phases.

Overall, the foundation is **solid**: data models are well-designed, tests are clean and passing (18/18), and the specification is thorough. There are a few issues worth addressing before building on this foundation.

## Critical Issues

*None identified.* The codebase is scaffolding-stage and introduces no security vulnerabilities or breaking issues.

## Major Issues

### Issue 1: `pyproject.toml` uses non-standard build backend — ✅ RESOLVED

- **File:** `pyproject.toml:3`
- **Severity:** Major
- **Resolution:** Changed to `setuptools.build_meta`.

### Issue 2: JournalEntry splits list is mutable despite frozen dataclass — ✅ RESOLVED

- **File:** `bookkeeping/models.py`
- **Severity:** Major
- **Resolution:** `splits` is now `tuple[JournalEntrySplit, ...]` with `__post_init__` that converts list input to tuple and validates splits sum to zero.

### Issue 3: ImportResult errors list is mutable despite frozen dataclass — ✅ RESOLVED

- **File:** `bookkeeping/models.py`
- **Severity:** Major
- **Resolution:** `errors` is now `tuple[str, ...]` with `default=()`.

### Issue 4: No validation on Rule.match_type or CategorizationSuggestion.confidence — ✅ RESOLVED

- **File:** `bookkeeping/models.py`
- **Severity:** Major
- **Resolution:** Added `Literal` types (`MatchType`, `Confidence`) and `__post_init__` runtime validation on both `Rule` and `CategorizationSuggestion`.

## Minor Issues

### Issue 5: No `__post_init__` validation on BankTransaction — ✅ RESOLVED

- **File:** `bookkeeping/models.py`
- **Severity:** Minor
- **Resolution:** Added `__post_init__` validating non-empty `verification_number` and `Decimal` types for `amount`/`balance`.

### Issue 6: `cli.py` always exits with code 0 — ✅ RESOLVED

- **File:** `bookkeeping/cli.py`
- **Severity:** Minor
- **Resolution:** Changed to `sys.exit(1)` for the stub (no command given = error).

### Issue 7: `.gitignore` is minimal — ✅ RESOLVED

- **File:** `.gitignore`
- **Severity:** Minor
- **Resolution:** Added `*.db`, `*.gnucash`, `rapporter/`, `.env`, `.idea/`, `.vscode/`.

### Issue 8: Test fixtures don't cover edge cases mentioned in spec — ✅ RESOLVED

- **File:** `tests/conftest.py`
- **Severity:** Minor
- **Resolution:** Added `sample_bank_transaction_3_decimal` fixture with `Decimal("-100.000")`.

### Issue 9: `account.csv` contains test/placeholder data

- **File:** `account.csv`
- **Severity:** Minor
- **Description:** No action needed now — will create realistic fixture in `tests/fixtures/sample_bank.csv` when integration tests are built.

### Issue 10: Swedish naming in code — ✅ RESOLVED

- **Severity:** Major (added post-review)
- **Description:** All code identifiers (package name, class names, field names, variable names) used Swedish words, mixing languages in the implementation.
- **Resolution:** Renamed package `bokforing` → `bookkeeping`, exception `BokforingError` → `BookkeepingError`, and all model fields to English (`booking_date`, `value_date`, `verification_number`, `amount`, `balance`, `entry_date`, `description`, `org_number`). Updated SPECIFICATION.md, all OpenSpec change documents, and CLAUDE.md. Added naming convention documentation to CLAUDE.md.

## Positive Highlights

- **Excellent specification quality**: The SPECIFICATION.md is comprehensive — 970 lines covering architecture, data models, APIs, security, testing strategy, and implementation plan. The VAT splitting examples with actual BAS account numbers are particularly useful.
- **Clean data model design**: Using frozen dataclasses for value objects and mutable dataclass for `Rule` is a well-considered pattern. The exception hierarchy with a common `BookkeepingError` base enables clean error handling.
- **Good test structure**: 30 tests covering immutability, validation, Decimal precision, exception hierarchy, and defaults — all passing. Well-organized with descriptive test classes.
- **Thorough OpenSpec workflow**: All 8 phases have complete proposal → design → spec → tasks artifacts, providing clear implementation roadmaps.
- **Domain-appropriate decisions**: Using `Decimal` everywhere (never float), semicolon-delimited CSV handling, and BAS 2023 chart of accounts show deep understanding of the Swedish bookkeeping domain.
- **Sensible architecture**: Separation of rules DB from GnuCash, automatic backup before writes, and the piecash integration choice are all pragmatic decisions.

## Specification Compliance

- ✅ Data models (BankTransaction, VATSplit, CategorizationSuggestion, JournalEntry, Rule, CompanyInfo, ImportResult): All defined per spec with English field names
- ✅ Exception hierarchy (BookkeepingError, CSVParseError, GnuCashError, RulesDBError): All defined per spec
- ✅ Project structure: Matches specified layout (`bookkeeping/` package, `tests/`)
- ✅ pyproject.toml: Standard build backend, dependencies, entry point, and test config present
- ✅ JournalEntry balance invariant: Enforced at construction via `__post_init__`
- ✅ Rule/Confidence validation: Constrained via `Literal` types and runtime validation
- ✅ English naming convention: All code identifiers use English; documented in CLAUDE.md
- ❌ CSV parser: Not yet implemented (Phase 1 - expected)
- ❌ Dedup module: Not yet implemented (Phase 1 - expected)
- ❌ Categorizer: Not yet implemented (Phase 1 - expected)
- ❌ Rules DB: Not yet implemented (Phase 1 - expected)
- ❌ GnuCash writer: Not yet implemented (Phase 1 - expected)
- ❌ VAT module: Not yet implemented (Phase 1 - expected)
- ❌ GTK4 app: Not yet implemented (Phase 2 - expected)
- ❌ Report generator: Not yet implemented (Phase 3 - expected)
- ❌ Full CLI: Not yet implemented (Phase 4 - expected)

*Note: The ❌ items above are expected — the project is in scaffolding stage with implementation planned through the OpenSpec change workflow.*

## Overall Recommendation

**APPROVE**

All identified issues have been resolved. The codebase is a well-structured foundation with English naming throughout, proper validation, true immutability, and comprehensive test coverage (30 tests, all passing). Ready to proceed with Phase 1 implementation.
