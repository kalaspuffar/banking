## ADDED Requirements

### Requirement: Python package with pyproject.toml
The project SHALL have a `pyproject.toml` at the repository root defining the package `bokforing` with Python ≥3.10 requirement, setuptools build backend, and all runtime dependencies (piecash ≥1.2.0, weasyprint ≥60.0, Jinja2 ≥3.1) and test dependencies (pytest ≥7.0).

#### Scenario: Package is pip-installable
- **WHEN** a user runs `pip install -e .` from the repository root
- **THEN** the `bokforing` package is installed and the `bokforing` CLI entry point is available

#### Scenario: Dependencies are declared
- **WHEN** the package is installed
- **THEN** piecash, weasyprint, and Jinja2 are installed as runtime dependencies

### Requirement: Package directory structure
The project SHALL have a `bokforing/` package directory containing `__init__.py` and `__main__.py`, and a `tests/` directory containing `__init__.py` and `conftest.py`.

#### Scenario: Package is importable
- **WHEN** Python code runs `import bokforing`
- **THEN** the import succeeds without error

#### Scenario: Package is runnable as module
- **WHEN** a user runs `python -m bokforing`
- **THEN** the `__main__.py` entry point executes (stub prints a usage message)

### Requirement: CLI entry point
The `pyproject.toml` SHALL define a console script entry point `bokforing` pointing to `bokforing.cli:main`.

#### Scenario: Entry point is registered
- **WHEN** the package is installed in editable mode
- **THEN** running `bokforing` from the command line invokes the CLI entry point

### Requirement: Test infrastructure
The project SHALL include a `tests/conftest.py` with shared pytest fixtures for sample BankTransaction objects, sample Rule objects, and temporary directory paths.

#### Scenario: Pytest discovers fixtures
- **WHEN** pytest runs from the repository root
- **THEN** fixtures from `tests/conftest.py` are available to all test modules
