## ADDED Requirements

### Requirement: Generate PDF report by type
The system SHALL provide a function `generate_report(report_type: str, gnucash_book_path: Path, fiscal_year: int, output_path: Path, company_info: CompanyInfo) -> Path` that generates a PDF report and returns the path to the generated file.

#### Scenario: Generate momsdeklaration report
- **WHEN** `generate_report` is called with `report_type="moms"`
- **THEN** it produces a PDF file at the output path containing the momsdeklaration summary for the given fiscal year

#### Scenario: Generate all report types
- **WHEN** `generate_report` is called with report_type of "moms", "ne", "grundbok", or "huvudbok"
- **THEN** each produces a valid PDF file without error

#### Scenario: Invalid report type
- **WHEN** `generate_report` is called with an unrecognized report_type
- **THEN** a ValueError is raised indicating the valid report types

### Requirement: Momsdeklaration with SKV 4700 ruta mapping
The system SHALL generate a momsdeklaration summary that maps GnuCash account totals to SKV 4700 form fields for the given fiscal year.

#### Scenario: Ruta 05 — Momspliktig försäljning 25%
- **WHEN** the GnuCash book contains sales on account 3010 totaling 80,000 SEK net
- **THEN** ruta 05 in the report shows 80,000

#### Scenario: Ruta 08 — Momsfri försäljning
- **WHEN** the GnuCash book contains VAT-exempt sales on account 3040 totaling 6,000 SEK
- **THEN** ruta 08 in the report shows 6,000

#### Scenario: Ruta 10 — Utgående moms 25%
- **WHEN** the GnuCash book contains output VAT on account 2610 totaling 20,000 SEK
- **THEN** ruta 10 in the report shows 20,000

#### Scenario: Ruta 48 — Ingående moms
- **WHEN** the GnuCash book contains input VAT on account 2640 totaling 3,500 SEK
- **THEN** ruta 48 in the report shows 3,500

#### Scenario: Ruta 49 — Moms att betala/få tillbaka
- **WHEN** ruta 10 is 20,000 and ruta 48 is 3,500
- **THEN** ruta 49 shows 16,500 (output VAT minus input VAT)

### Requirement: NE-bilaga with INK1 ruta mapping
The system SHALL generate an NE-bilaga summary that maps GnuCash account totals to INK1 NE form fields for the given fiscal year.

#### Scenario: R1 — Nettoomsättning
- **WHEN** the GnuCash book contains revenue on accounts 30xx totaling 86,000 SEK
- **THEN** ruta R1 in the report shows 86,000

#### Scenario: R5 — Övriga externa kostnader
- **WHEN** the GnuCash book contains costs on accounts 50xx-69xx totaling 15,000 SEK
- **THEN** ruta R5 in the report shows 15,000

#### Scenario: R7 — Bokfört resultat
- **WHEN** R1=86,000, R2=0, R5=15,000, R6=0
- **THEN** ruta R7 shows 71,000 (R1+R2-R5-R6)

#### Scenario: B1 and B4 — Eget kapital
- **WHEN** account 2010 has an opening balance of 50,000 and closing balance of 121,000
- **THEN** ruta B1 shows 50,000 and ruta B4 shows 121,000

### Requirement: Grundbok — chronological journal
The system SHALL generate a grundbok report listing all transactions for the fiscal year in chronological order.

#### Scenario: Transactions sorted by date and verification_number
- **WHEN** the GnuCash book contains transactions on multiple dates
- **THEN** the grundbok lists them sorted by date first, then by verification_number

#### Scenario: Transaction columns
- **WHEN** a transaction is rendered in the grundbok
- **THEN** it shows: Verifikation, Datum, Text, Konto (account number + name), Debet, and Kredit

#### Scenario: Page totals and grand totals
- **WHEN** the grundbok spans multiple pages
- **THEN** each page shows page totals for debet and kredit, and the last page shows grand totals

### Requirement: Huvudbok — per-account general ledger
The system SHALL generate a huvudbok report grouping all transactions by BAS account for the fiscal year.

#### Scenario: Account sections with headers
- **WHEN** account 1930 has transactions
- **THEN** it appears as a section with the header "1930 Företagskonto / checkkonto"

#### Scenario: Opening and closing balances
- **WHEN** an account section is rendered
- **THEN** it shows the opening balance at the top, all transactions, and the closing balance at the bottom

#### Scenario: Account subtotals
- **WHEN** an account section lists its transactions
- **THEN** it includes subtotals for debet and kredit amounts

#### Scenario: Sorted by account number
- **WHEN** the huvudbok is generated
- **THEN** account sections are ordered by account number ascending

### Requirement: Company info in all reports
The system SHALL include company information (name, organisationsnummer, address, fiscal year) in the header of every generated report.

#### Scenario: Report header content
- **WHEN** any report is generated with company_info containing name="Test AB" and org_number="551234-5678"
- **THEN** the PDF header shows "Test AB" and "551234-5678"

### Requirement: Page numbers in all reports
The system SHALL include page numbers in the format "Sida X av Y" in the footer of every generated report.

#### Scenario: Multi-page report pagination
- **WHEN** a grundbok report spans 5 pages
- **THEN** each page footer shows "Sida 1 av 5", "Sida 2 av 5", etc.

### Requirement: Totals verified against GnuCash
The system SHALL ensure that all monetary totals in the reports are derived from GnuCash data using Decimal arithmetic, and that the grundbok grand totals for debet and kredit are equal (balanced).

#### Scenario: Balanced grundbok totals
- **WHEN** the grundbok grand totals are computed
- **THEN** total debet equals total kredit

#### Scenario: Decimal precision
- **WHEN** amounts are aggregated for any report
- **THEN** all calculations use Decimal with öre (2 decimal places) precision
