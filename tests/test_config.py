"""Unit tests for bookkeeping.config.ConfigManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from bookkeeping.config import ConfigManager
from bookkeeping.models import CompanyInfo


@pytest.fixture()
def config_manager(tmp_path: Path) -> ConfigManager:
    """Provide a ConfigManager backed by a temporary database."""
    db_path = tmp_path / "test_rules.db"
    with ConfigManager(db_path) as cm:
        yield cm


class TestGetSet:
    """Test basic get/set behaviour."""

    def test_set_and_get_returns_value(self, config_manager: ConfigManager) -> None:
        config_manager.set("company_name", "Mitt Företag AB")
        assert config_manager.get("company_name") == "Mitt Företag AB"

    def test_get_missing_key_returns_none(self, config_manager: ConfigManager) -> None:
        assert config_manager.get("nonexistent") is None

    def test_get_missing_key_with_default(self, config_manager: ConfigManager) -> None:
        assert config_manager.get("nonexistent", "/default/path") == "/default/path"

    def test_set_overwrites_existing_value(self, config_manager: ConfigManager) -> None:
        config_manager.set("org_number", "111111-1111")
        config_manager.set("org_number", "222222-2222")
        assert config_manager.get("org_number") == "222222-2222"

    def test_set_and_get_multiple_keys(self, config_manager: ConfigManager) -> None:
        config_manager.set("key_a", "value_a")
        config_manager.set("key_b", "value_b")
        assert config_manager.get("key_a") == "value_a"
        assert config_manager.get("key_b") == "value_b"


class TestGetAll:
    """Test get_all returns all config pairs."""

    def test_get_all_empty(self, config_manager: ConfigManager) -> None:
        assert config_manager.get_all() == {}

    def test_get_all_returns_stored_pairs(self, config_manager: ConfigManager) -> None:
        config_manager.set("company_name", "Test AB")
        config_manager.set("org_number", "123456-7890")
        result = config_manager.get_all()
        assert result == {
            "company_name": "Test AB",
            "org_number": "123456-7890",
        }


class TestTableCreationIdempotency:
    """Test that ConfigManager can be created multiple times on the same db."""

    def test_reopening_preserves_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"

        with ConfigManager(db_path) as cm:
            cm.set("company_name", "Preserved AB")

        with ConfigManager(db_path) as cm:
            assert cm.get("company_name") == "Preserved AB"

    def test_double_init_does_not_raise(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        cm1 = ConfigManager(db_path)
        cm1.close()
        cm2 = ConfigManager(db_path)
        cm2.close()


class TestFindDefaultBookPath:
    """Test find_default_book_path discovery logic."""

    def test_returns_none_when_dir_missing(self, config_manager: ConfigManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "no_home")
        assert config_manager.find_default_book_path() is None

    def test_returns_none_when_no_gnucash_files(self, config_manager: ConfigManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gnucash_dir = tmp_path / ".local" / "share" / "gnucash"
        gnucash_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert config_manager.find_default_book_path() is None

    def test_returns_gnucash_file_when_found(self, config_manager: ConfigManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gnucash_dir = tmp_path / ".local" / "share" / "gnucash"
        gnucash_dir.mkdir(parents=True)
        book_file = gnucash_dir / "mybook.gnucash"
        book_file.touch()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert config_manager.find_default_book_path() == book_file


class TestGetCompanyInfo:
    """Test CompanyInfo construction from config."""

    def test_returns_company_info_with_stored_values(self, config_manager: ConfigManager) -> None:
        config_manager.set("company_name", "Test AB")
        config_manager.set("org_number", "123456-7890")
        config_manager.set("company_address", "Storgatan 1, 111 22 Stockholm")

        info = config_manager.get_company_info(fiscal_year=2025)

        assert info == CompanyInfo(
            name="Test AB",
            org_number="123456-7890",
            address="Storgatan 1, 111 22 Stockholm",
            fiscal_year=2025,
        )

    def test_returns_empty_strings_when_config_missing(self, config_manager: ConfigManager) -> None:
        info = config_manager.get_company_info(fiscal_year=2024)

        assert info.name == ""
        assert info.org_number == ""
        assert info.address == ""
        assert info.fiscal_year == 2024
