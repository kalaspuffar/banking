"""Configuration management for the bookkeeping tool.

Reads and writes configuration key-value pairs from the ``config`` table in
rules.db. Also provides helper methods for resolving default GnuCash book
paths and constructing CompanyInfo objects for report generation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bookkeeping.models import CompanyInfo, RulesDBError

_CREATE_CONFIG_TABLE = """\
CREATE TABLE IF NOT EXISTS config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""


class ConfigManager:
    """Read and write configuration stored in the rules.db config table.

    The config table is created automatically if it does not exist, making
    initialisation idempotent.

    Args:
        db_path: Path to the SQLite database file (typically rules.db).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(_CREATE_CONFIG_TABLE)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(
                f"Failed to initialise config in {db_path}: {exc}"
            ) from exc

        # Enforce owner-only permissions (NF-SEC-03) regardless of whether
        # the database was just created or already existed.
        self._db_path.chmod(0o600)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> ConfigManager:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a configuration value by key.

        Args:
            key: The configuration key to look up.
            default: Value to return when the key does not exist.

        Returns:
            The stored value string, or *default* if the key is missing.
        """
        try:
            cursor = self._conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row is not None else default
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to read config key {key!r}: {exc}") from exc

    def set(self, key: str, value: str) -> None:
        """Store a configuration value, inserting or updating as needed.

        Args:
            key: The configuration key.
            value: The value to store.
        """
        try:
            self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to set config key {key!r}: {exc}") from exc

    def get_all(self) -> dict[str, str]:
        """Return all configuration key-value pairs.

        Returns:
            Dictionary of all stored configuration values.
        """
        try:
            cursor = self._conn.execute("SELECT key, value FROM config ORDER BY key")
            return {row["key"]: row["value"] for row in cursor.fetchall()}
        except sqlite3.Error as exc:
            raise RulesDBError(f"Failed to read config: {exc}") from exc

    def find_default_book_path(self) -> Path | None:
        """Search common locations for a GnuCash book file.

        Looks in ``~/.local/share/gnucash/`` for files with a ``.gnucash``
        extension.

        Returns:
            Path to the first ``.gnucash`` file found, or ``None`` if no
            file is found.
        """
        gnucash_dir = Path.home() / ".local" / "share" / "gnucash"
        if not gnucash_dir.is_dir():
            return None

        gnucash_files = sorted(gnucash_dir.glob("*.gnucash"))
        return gnucash_files[0] if gnucash_files else None

    def get_company_info(self, fiscal_year: int) -> CompanyInfo:
        """Construct a CompanyInfo dataclass from stored config values.

        Args:
            fiscal_year: The fiscal year for the report.

        Returns:
            A CompanyInfo populated from the config table.
        """
        return CompanyInfo(
            name=self.get("company_name", ""),
            org_number=self.get("org_number", ""),
            address=self.get("company_address", ""),
            fiscal_year=fiscal_year,
        )
