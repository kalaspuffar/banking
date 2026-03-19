## Context

This is a greenfield Python project for Swedish bookkeeping automation. The SPECIFICATION.md defines the complete architecture, but no code exists yet. Every feature module (csv_parser, categorizer, gnucash_writer, etc.) depends on shared data models and a properly configured package. This change establishes that foundation.

The target environment is Debian/Ubuntu Linux with Python ≥3.10 and GnuCash (SQLite backend).

## Goals / Non-Goals

**Goals:**
- Establish a pip-installable Python package with correct metadata and dependency declarations
- Define all shared data model classes with full type annotations
- Provide the `bookkeeping` CLI entry point (stub — actual CLI logic comes in a later phase)
- Set up the test infrastructure (pytest, conftest fixtures)

**Non-Goals:**
- Implementing any business logic (parsing, categorization, writing, reporting)
- GTK4 GUI code
- HTML/PDF templates
- CLI argument parsing (beyond the entry point stub)

## Decisions

### 1. Use `pyproject.toml` (PEP 621) with setuptools backend
**Rationale**: Modern standard for Python packaging. No need for `setup.py` or `setup.cfg`. Setuptools is the most widely supported backend and requires no additional tooling.
**Alternative considered**: Poetry — adds a lock file and virtual env management, but overkill for a single-developer local tool.

### 2. All models as frozen dataclasses
**Rationale**: The data models (BankTransaction, JournalEntry, etc.) are value objects — they should be immutable after creation. Frozen dataclasses enforce this and are hashable by default, which is useful for deduplication sets.
**Alternative considered**: Pydantic — provides validation but adds a dependency and complexity not needed here since validation happens at the parsing boundary.

### 3. Use `Decimal` for all monetary amounts
**Rationale**: Required by SPECIFICATION.md to avoid float rounding errors. Swedish öre precision (2 decimal places) with banker's rounding (`ROUND_HALF_EVEN`).

### 4. Custom exception hierarchy rooted in `BookkeepingError`
**Rationale**: All modules can raise domain-specific exceptions that callers can catch broadly or narrowly. `CSVParseError`, `GnuCashError`, etc. all inherit from a common base.

### 5. Place shared fixtures in `tests/conftest.py`
**Rationale**: pytest auto-discovers conftest.py fixtures. Centralizing sample `BankTransaction` objects, temporary directory paths, and Rule instances avoids duplication across test modules.

## Risks / Trade-offs

- **[Risk] Frozen dataclasses may be inconvenient for the GTK GUI** → Mitigation: The GUI will work with mutable view-model objects that wrap the frozen models. The core data flow remains immutable.
- **[Risk] piecash dependency may conflict with system Python packages** → Mitigation: Document `pip install --user` or venv usage in README. piecash has minimal transitive dependencies.
- **[Risk] Model definitions may need revision as implementation proceeds** → Mitigation: Models are internal (no public API consumers), so changes are low-cost. The spec is detailed enough that major revisions are unlikely.
