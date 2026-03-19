## ADDED Requirements

### Requirement: ConfigManager class
The system SHALL provide a `ConfigManager` class in `bokforing/config.py` that reads and writes configuration key-value pairs from the `config` table in rules.db.

#### Scenario: Read existing config value
- **WHEN** `config_manager.get("gnucash_book_path")` is called and the key exists
- **THEN** the stored value string is returned

#### Scenario: Read missing config value with default
- **WHEN** `config_manager.get("gnucash_book_path", default="/default/path")` is called and the key does not exist
- **THEN** the default value `"/default/path"` is returned

#### Scenario: Read missing config value without default
- **WHEN** `config_manager.get("nonexistent_key")` is called without a default
- **THEN** `None` is returned

#### Scenario: Set config value
- **WHEN** `config_manager.set("company_name", "Mitt Företag")` is called
- **THEN** the key-value pair is stored in the config table (inserted or updated if already exists)

### Requirement: Supported config keys
The system SHALL support the following configuration keys: `gnucash_book_path`, `company_name`, `org_nummer`, `company_address`.

#### Scenario: All config keys are settable and retrievable
- **WHEN** each supported key is set via `config_manager.set()` and then read via `config_manager.get()`
- **THEN** the retrieved values match what was set

### Requirement: Config table creation
The `ConfigManager` SHALL create the `config` table if it does not already exist in the database, making initialization idempotent.

#### Scenario: ConfigManager with fresh database
- **WHEN** `ConfigManager` is initialized with a database that has no `config` table
- **THEN** the config table is created automatically and operations proceed normally

#### Scenario: ConfigManager with existing database
- **WHEN** `ConfigManager` is initialized with a database that already has a `config` table
- **THEN** the existing table and data are preserved

### Requirement: Default GnuCash book path resolution
The system SHALL provide a method to resolve a default GnuCash book path by searching common locations: `~/.local/share/gnucash/` for `.gnucash` files.

#### Scenario: GnuCash book found in default location
- **WHEN** `config_manager.find_default_book_path()` is called and a `.gnucash` file exists in `~/.local/share/gnucash/`
- **THEN** the path to that file is returned

#### Scenario: No GnuCash book found
- **WHEN** `config_manager.find_default_book_path()` is called and no `.gnucash` files are found in default locations
- **THEN** `None` is returned

### Requirement: CompanyInfo construction from config
The system SHALL provide a method to construct a `CompanyInfo` dataclass instance from the stored configuration values.

#### Scenario: Build CompanyInfo from config
- **WHEN** `config_manager.get_company_info(fiscal_year=2025)` is called with all config keys set
- **THEN** a `CompanyInfo` object is returned with name, org_nummer, address, and the specified fiscal_year
