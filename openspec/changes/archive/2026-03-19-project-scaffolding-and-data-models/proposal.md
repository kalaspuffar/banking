## Why

The project has a complete specification (SPECIFICATION.md) but no code yet. Before any feature module can be built, we need the Python package structure, build configuration, and shared data model classes that every other component depends on. This is the foundational step that unblocks all subsequent implementation phases.

## What Changes

- Create `pyproject.toml` with package metadata, dependencies (piecash, weasyprint, Jinja2, pytest), and entry point (`bookkeeping` CLI command)
- Create the `bookkeeping/` package directory with `__init__.py` and `__main__.py`
- Implement all shared data models in `bookkeeping/models.py`: `BankTransaction`, `CategorizationSuggestion`, `JournalEntrySplit`, `JournalEntry`, `Rule`, `CompanyInfo`, `ImportResult`, and the `CSVParseError` exception
- Create `tests/conftest.py` with shared pytest fixtures (sample transactions, sample rules, temporary paths)
- Create `tests/__init__.py`

## Capabilities

### New Capabilities
- `project-structure`: Python package scaffolding — pyproject.toml, package directories, entry point configuration
- `data-models`: Shared dataclass definitions and custom exceptions used across all modules

### Modified Capabilities
<!-- None — this is a greenfield project with no existing specs. -->

## Impact

- **Code**: Creates the entire `bookkeeping/` package and `tests/` directory from scratch
- **Dependencies**: Defines the project's Python dependency tree (piecash ≥1.2.0, weasyprint ≥60.0, Jinja2 ≥3.1, pytest ≥7.0)
- **APIs**: Establishes the data contracts (dataclass interfaces) that csv_parser, categorizer, gnucash_writer, and all other modules will consume
- **Systems**: Requires Python ≥3.10 on Debian/Ubuntu Linux
