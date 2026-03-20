"""Integration tests for the bookkeeping CLI.

Tests cover argument parsing, the init wizard (with mocked input), import
dry-run mode, config show/set, and rules list. Also verifies exit code
behaviour for error paths.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from bookkeeping.cli import (
    EXIT_CSV_ERROR,
    EXIT_GNUCASH_ERROR,
    EXIT_SUCCESS,
    EXIT_USER_CANCELLED,
    _build_parser,
    _handle_config,
    _handle_init,
    _handle_rules,
    _DEFAULT_DB_PATH,
    main,
)
from bookkeeping.config import ConfigManager


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestArgumentParsing:
    """Verify argparse structure matches specification."""

    def setup_method(self) -> None:
        self.parser = _build_parser()

    def test_import_subcommand_parses(self) -> None:
        args = self.parser.parse_args(["import", "test.csv"])
        assert args.command == "import"
        assert args.csv_file == "test.csv"
        assert args.dry_run is False
        assert args.no_gui is False
        assert args.book is None

    def test_import_with_all_flags(self) -> None:
        args = self.parser.parse_args([
            "import", "data.csv", "--book", "/tmp/b.gnucash",
            "--dry-run", "--no-gui",
        ])
        assert args.csv_file == "data.csv"
        assert args.book == "/tmp/b.gnucash"
        assert args.dry_run is True
        assert args.no_gui is True

    def test_report_subcommand_parses(self) -> None:
        args = self.parser.parse_args(["report", "moms", "2025"])
        assert args.command == "report"
        assert args.type == "moms"
        assert args.year == "2025"

    def test_report_all_type(self) -> None:
        args = self.parser.parse_args(["report", "all", "2024"])
        assert args.type == "all"

    def test_report_invalid_type_raises(self) -> None:
        with pytest.raises(SystemExit):
            self.parser.parse_args(["report", "invalid", "2025"])

    def test_report_with_output_dir(self) -> None:
        args = self.parser.parse_args([
            "report", "ne", "2025", "--output-dir", "/tmp/out",
        ])
        assert args.output_dir == "/tmp/out"

    def test_rules_list_subcommand(self) -> None:
        args = self.parser.parse_args(["rules", "list"])
        assert args.command == "rules"
        assert args.rules_command == "list"

    def test_rules_delete_subcommand(self) -> None:
        args = self.parser.parse_args(["rules", "delete", "5"])
        assert args.rules_command == "delete"
        assert args.rule_id == 5

    def test_rules_export_subcommand(self) -> None:
        args = self.parser.parse_args(["rules", "export", "backup.json"])
        assert args.rules_command == "export"
        assert args.file == "backup.json"

    def test_rules_import_subcommand(self) -> None:
        args = self.parser.parse_args(["rules", "import", "backup.json"])
        assert args.rules_command == "import"
        assert args.file == "backup.json"

    def test_config_show_subcommand(self) -> None:
        args = self.parser.parse_args(["config", "show"])
        assert args.command == "config"
        assert args.config_command == "show"

    def test_config_set_subcommand(self) -> None:
        args = self.parser.parse_args(["config", "set", "company_name", "Test AB"])
        assert args.config_command == "set"
        assert args.key == "company_name"
        assert args.value == "Test AB"

    def test_init_subcommand(self) -> None:
        args = self.parser.parse_args(["init"])
        assert args.command == "init"

    def test_no_command_prints_help(self) -> None:
        args = self.parser.parse_args([])
        assert args.command is None


# ---------------------------------------------------------------------------
# Init wizard tests (mocked input)
# ---------------------------------------------------------------------------


class TestInitWizard:
    """Test the init wizard with mocked user input."""

    def test_init_creates_db_and_stores_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DATA_DIR", tmp_path)
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        inputs = iter([
            "/home/user/book.gnucash",  # GnuCash book path
            "Test AB",                   # Company name
            "123456-7890",              # Org number
            "Storgatan 1",              # Address
        ])
        monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

        # Create a fake gnucash file so validation passes
        # (init warns but still saves if file not found)
        parser = _build_parser()
        args = parser.parse_args(["init"])
        _handle_init(args)

        with ConfigManager(db_path) as cm:
            assert cm.get("company_name") == "Test AB"
            assert cm.get("org_number") == "123456-7890"
            assert cm.get("company_address") == "Storgatan 1"
            assert cm.get("gnucash_book_path") == "/home/user/book.gnucash"

    def test_init_rerun_shows_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DATA_DIR", tmp_path)
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        # Pre-populate config
        with ConfigManager(db_path) as cm:
            cm.set("company_name", "Old Name")
            cm.set("org_number", "111111-1111")
            cm.set("company_address", "Old Address")
            cm.set("gnucash_book_path", "/old/path.gnucash")

        # User presses Enter on all prompts to keep defaults
        monkeypatch.setattr("builtins.input", lambda _prompt: "")

        parser = _build_parser()
        args = parser.parse_args(["init"])
        _handle_init(args)

        with ConfigManager(db_path) as cm:
            assert cm.get("company_name") == "Old Name"
            assert cm.get("gnucash_book_path") == "/old/path.gnucash"


# ---------------------------------------------------------------------------
# Config show/set tests
# ---------------------------------------------------------------------------


class TestConfigCommands:
    """Test config show and set subcommands."""

    def test_config_set_and_show(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        parser = _build_parser()

        # Set a value
        args = parser.parse_args(["config", "set", "company_name", "TestCo"])
        _handle_config(args)

        captured = capsys.readouterr()
        assert "Set company_name = TestCo" in captured.out

        # Show config
        args = parser.parse_args(["config", "show"])
        _handle_config(args)

        captured = capsys.readouterr()
        assert "company_name" in captured.out
        assert "TestCo" in captured.out

    def test_config_show_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        parser = _build_parser()
        args = parser.parse_args(["config", "show"])
        _handle_config(args)

        captured = capsys.readouterr()
        assert "No configuration set" in captured.out


# ---------------------------------------------------------------------------
# Rules list test
# ---------------------------------------------------------------------------


class TestRulesCommands:
    """Test rules subcommands."""

    def test_rules_list_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        parser = _build_parser()
        args = parser.parse_args(["rules", "list"])
        _handle_rules(args)

        captured = capsys.readouterr()
        assert "No rules found" in captured.out

    def test_rules_list_with_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        from datetime import date
        from decimal import Decimal
        from bookkeeping.models import Rule
        from bookkeeping.rules_db import RulesDatabase

        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        with RulesDatabase(db_path) as db:
            db.save_rule(Rule(
                id=None, pattern="spotify", match_type="contains",
                debit_account=6540, credit_account=1930,
                vat_rate=Decimal("0.25"), vat_account=2640,
                last_used=date.today(), use_count=3,
            ))

        parser = _build_parser()
        args = parser.parse_args(["rules", "list"])
        _handle_rules(args)

        captured = capsys.readouterr()
        assert "spotify" in captured.out
        assert "6540" in captured.out
        assert "1930" in captured.out


# ---------------------------------------------------------------------------
# Import dry-run test
# ---------------------------------------------------------------------------


class TestImportDryRun:
    """Test import --dry-run mode."""

    def test_dry_run_parses_and_prints_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        # Create a sample CSV
        csv_content = (
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2025-01-15;2025-01-15;99999;Spotify;-125.00;9875.00\n"
        )
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        book_path = tmp_path / "test.gnucash"
        book_path.touch()

        # Mock filter_duplicates at its source module since it's imported
        # locally inside _handle_import
        monkeypatch.setattr(
            "bookkeeping.dedup.filter_duplicates",
            lambda txns, _path: (txns, []),
        )

        monkeypatch.setattr(
            "bookkeeping.cli._resolve_book_path",
            lambda _book: book_path,
        )

        from bookkeeping.cli import _handle_import
        parser = _build_parser()
        args = parser.parse_args([
            "import", str(csv_path), "--dry-run", "--book", str(book_path),
        ])
        _handle_import(args)

        captured = capsys.readouterr()
        assert "Parsed 1 transactions" in captured.out
        assert "Dry-run summary" in captured.out
        assert "Spotify" in captured.out


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Test that errors produce correct exit codes."""

    def test_csv_parse_error_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Create a malformed CSV
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("not;a;valid;csv\nheader\n", encoding="utf-8")

        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["bookkeeping", "import", str(csv_path), "--dry-run"]):
                main()

        assert exc_info.value.code == EXIT_CSV_ERROR

    def test_gnucash_error_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        csv_content = (
            "Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo\n"
            "2025-01-15;2025-01-15;99999;Test;-100.00;9900.00\n"
        )
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        db_path = tmp_path / "rules.db"
        monkeypatch.setattr("bookkeeping.cli._DEFAULT_DB_PATH", db_path)

        # Set a book path that doesn't exist to trigger GnuCash error path
        with ConfigManager(db_path) as cm:
            cm.set("gnucash_book_path", str(tmp_path / "nonexistent.gnucash"))

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["bookkeeping", "import", str(csv_path)]):
                main()

        assert exc_info.value.code == EXIT_GNUCASH_ERROR

    def test_no_command_exits_1(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["bookkeeping"]):
                main()

        assert exc_info.value.code == EXIT_CSV_ERROR
